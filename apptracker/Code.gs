/**
 * JobRadar — Application Tracker
 * Auto-logs job-application confirmation emails from Gmail into this Sheet.
 *
 * Setup (one time):
 *   1) Make a Google Sheet (sheets.new) in the SAME Google account that gets
 *      these emails. 2) Extensions → Apps Script. 3) Paste this file.
 *   4) Run `setup` once and approve the permissions.
 * After that it runs every hour on its own. Run `processApplications` anytime
 * to update immediately.
 */

var SHEET_NAME      = 'Applications';
var PROCESSED_LABEL = 'JobRadar-Logged';
var LOOKBACK        = 'newer_than:1y';
// Used to fill in a job link when the email doesn't contain one:
var JOBS_URL        = 'https://dipeshk47.github.io/jobradar/jobs.json';

var HEADERS = ['Date Applied', 'Company', 'Role', 'Status', 'Job Link', 'Source', 'Email Subject'];

var NOISE = /graduate studies|to graduate|Penn Engineering|commencement|I-?20|\bOPT\b|Office of Global Services|Members Meeting|Capstone Competition|decision letter|Yankee Stadium|verify your email|reset your password|newsletter|unsubscribe preferences/i;

function setup() {
  ensureSheet_();
  ensureLabel_();
  processApplications();
  // (re)create a single hourly trigger
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'processApplications') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('processApplications').timeBased().everyHours(1).create();
  SpreadsheetApp.getActiveSpreadsheet().toast('Setup done — tracking hourly.', 'JobRadar', 5);
}

function ensureSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
  if (sh.getLastRow() === 0) {
    sh.appendRow(HEADERS);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold').setBackground('#f5f5f7');
    sh.setFrozenRows(1);
    sh.setColumnWidth(2, 180); sh.setColumnWidth(3, 240); sh.setColumnWidth(5, 320);
  }
  return sh;
}

function ensureLabel_() {
  return GmailApp.getUserLabelByName(PROCESSED_LABEL) || GmailApp.createLabel(PROCESSED_LABEL);
}

function processApplications() {
  var sh = ensureSheet_();
  var label = ensureLabel_();
  var query = LOOKBACK + ' -label:' + PROCESSED_LABEL + ' (' +
    '"your application was sent to" OR "your application to" OR ' +
    '"thank you for applying" OR "received your application" OR ' +
    '"application was submitted" OR "application has been received" OR ' +
    '"thank you for your interest in joining" OR "application was submitted successfully"' +
    ')';

  var threads = GmailApp.search(query, 0, 150);
  if (!threads.length) return;

  var jobs = fetchJobs_();           // for link enrichment (fetched once per run)
  var rows = [];
  threads.forEach(function (th) {
    var info = extractApplication_(th, jobs);
    if (info) {
      rows.push([info.date, info.company, info.role, info.status, info.link, info.source, info.subject]);
      th.addLabel(label);            // only mark threads we actually logged
    }
  });
  if (rows.length) {
    sh.getRange(sh.getLastRow() + 1, 1, rows.length, HEADERS.length).setValues(rows);
    // newest first
    sh.getRange(2, 1, sh.getLastRow() - 1, HEADERS.length).sort({ column: 1, ascending: false });
  }
}

function extractApplication_(thread, jobs) {
  var msgs = thread.getMessages();
  var first = msgs[0];
  var subject = first.getSubject() || '';
  var from = first.getFrom() || '';
  var body = first.getPlainBody() || '';
  var text = subject + '\n' + body;

  if (NOISE.test(text)) return null;

  var company = '', role = '', m;

  if ((m = subject.match(/your application to (.+?) at (.+)$/i))) { role = m[1]; company = m[2]; }
  if (!company && (m = subject.match(/your application was sent to (.+)$/i))) { company = m[1]; }
  if (!company && (m = text.match(/applying (?:for|to)\s+(?:the\s+)?(.+?)\s+(?:role|position)\s+at\s+(.+?)(?:[.!\n]|$)/i))) { role = role || m[1]; company = m[2]; }
  if (!company && (m = text.match(/interest in joining\s+(.+?)[!.\n]/i))) { company = m[1]; }
  if (!role && (m = text.match(/application for the (.+?) (?:job|role|position) was submitted/i))) { role = m[1]; }
  if (!role && (m = text.match(/applying for the role of (.+?)[.!\n]/i))) { role = m[1]; }

  if (!company) company = senderCompany_(from);

  company = (company || '').replace(/\s*\|.*$/, '').replace(/&amp;/g, '&').replace(/[.,!]+$/, '').trim();
  role = (role || '').replace(/&amp;/g, '&').replace(/[.,!]+$/, '').trim();
  if (!company) return null;

  // status from the whole thread
  var threadText = msgs.map(function (x) { return x.getSubject() + ' ' + x.getPlainBody(); }).join('\n');
  var status = 'Applied';
  if (/regret to inform|not been selected|isn'?t an ideal fit|not an? ideal fit|will not be moving forward|decided not to/i.test(threadText)) status = 'Rejected';
  else if (/schedule (a|an|your)|move to the next step|move forward|next steps?|set up (a|an)? ?(call|interview|chat)/i.test(threadText)) status = 'Interview';

  var link = findJobLink_(body) || matchJobLink_(jobs, company, role) || '';

  return {
    date: Utilities.formatDate(first.getDate(), Session.getScriptTimeZone(), 'yyyy-MM-dd'),
    company: company, role: role || '—', status: status, link: link,
    source: senderDomain_(from), subject: subject
  };
}

function senderCompany_(from) {
  var name = (from.match(/^\s*"?([^"<]+?)"?\s*</) || [, ''])[1].trim();
  if (/no-?reply|notifications?|careers?|talent|recruiting|jobs|team|hr|people|hello|info|do-?not-?reply/i.test(name) || !name) {
    var dom = senderDomain_(from);
    var ats = /greenhouse|lever|ashbyhq|myworkdayjobs|workday|smartrecruiters|workable|icims|gmail|linkedin|spark.?hire/i;
    if (dom && !ats.test(dom)) return dom.split('.')[0].replace(/^\w/, function (c) { return c.toUpperCase(); });
  }
  return name || '';
}

function senderDomain_(from) {
  var m = from.match(/@([\w.-]+)/);
  return m ? m[1].replace(/^mail\.|^careers\.|^jobs\./, '') : '';
}

function findJobLink_(body) {
  if (!body) return '';
  var urls = body.match(/https?:\/\/[^\s<>"')\]]+/g) || [];
  var clean = urls.filter(function (u) { return !/unsubscribe|privacy|notification|settings|\.png|\.jpg|\.gif|\.svg|logo|mailto|facebook|twitter|linkedin\.com\/company|instagram/i.test(u); });
  var prefer = clean.filter(function (u) { return /greenhouse|lever\.co|ashbyhq|myworkdayjobs|linkedin\.com\/(comm\/)?jobs|jobs\.|\/careers|workable|smartrecruiters|\/job/i.test(u); });
  return ((prefer[0] || clean[0]) || '').replace(/[).,]+$/, '');
}

function fetchJobs_() {
  try { return JSON.parse(UrlFetchApp.fetch(JOBS_URL, { muteHttpExceptions: true }).getContentText()); }
  catch (e) { return []; }
}

function matchJobLink_(jobs, company, role) {
  if (!jobs || !jobs.length || !company) return '';
  var c = company.toLowerCase(), rw = (role || '').toLowerCase().split(/\s+/)[0] || '';
  var hit = jobs.filter(function (j) {
    var jc = (j.company || '').toLowerCase();
    return jc && (jc === c || jc.indexOf(c) > -1 || c.indexOf(jc) > -1);
  });
  if (rw) {
    var withRole = hit.filter(function (j) { return (j.title || '').toLowerCase().indexOf(rw) > -1; });
    if (withRole.length) return withRole[0].url || '';
  }
  return hit.length ? (hit[0].url || '') : '';
}
