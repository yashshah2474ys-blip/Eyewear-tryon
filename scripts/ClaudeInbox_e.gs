var SAME_DAY_PARTIES = ['RIAZ', 'RIYAZ', 'HANI', 'MUNNA', 'ASGAR', 'ASGHAR', 'YUSUF', 'YOUSUF'];
/* ================= v19e: same-day parties (RIAZ, HANI, MUNNA, ASGAR, YUSUF) go into today's slip.  v19d: 📥 Load slip from Claude – loads AND finishes, one slip or ALL at once ================= */
function loadClaudeSlip() {
  var ui = SpreadsheetApp.getUi(), ss = SpreadsheetApp.getActiveSpreadsheet(), cfg = ss.getSheetByName('_CONFIG');
  if (slipOpen_(ss)) { ui.alert('A slip is still open', 'Press ✅ Finish slip for the current slip first, then load.', ui.ButtonSet.OK); return; }
  var pnd = ss.getSheetByName('_PENDING');
  if (pnd && pnd.getLastRow() > 0 && pnd.getRange(1, 1, pnd.getLastRow(), 1).getValues().some(function (r) { return r[0]; })) {
    ui.alert('Typed boxes are waiting', 'Some typed (yellow) entries are not posted yet. Press 📤 Post typed entries now (or finish them), then load from Claude.', ui.ButtonSet.OK); return; }
  var files = [], it = DriveApp.searchFiles("title contains 'CLAUDE SLIP' and mimeType = 'text/csv' and trashed = false");
  while (it.hasNext()) { var f = it.next(); files.push({ f: f, rows: Utilities.parseCsv(f.getBlob().getDataAsString()) }); }
  var ids = [], info = {};
  files.forEach(function (F, fi) { F.rows.forEach(function (x, i) {
    if (i === 0 || !x[0] || x[1] !== 'READY') return;
    var key = fi + '|' + x[0];
    if (!info[key]) { info[key] = { fi: fi, id: x[0], party: x[2], n: 0, prs: 0 }; ids.push(key); }
    info[key].n++; info[key].prs += Number(x[7]) || 0; }); });
  if (!ids.length) { ui.alert('Nothing waiting', 'No slips from Claude are waiting.', ui.ButtonSet.OK); return; }
  var list = ids.map(function (k, i) { return (i + 1) + ')  ' + info[k].party + '  —  ' + info[k].n + ' lines, ' + Math.round(info[k].prs * 100) / 100 + ' prs'; }).join('\n');
  var ans = ui.prompt('📥 Slips from Claude', list + '\n\nType A to post ALL, or the number of one slip:', ui.ButtonSet.OK_CANCEL);
  if (ans.getSelectedButton() !== ui.Button.OK) return;
  var t = String(ans.getResponseText()).trim().toUpperCase(), pick = [];
  if (t === 'A') pick = ids.slice(); else { var k = parseInt(t, 10); if (!(k >= 1 && k <= ids.length)) { ui.alert('No slip number ' + t); return; } pick = [ids[k - 1]]; }
  var stop = false, done = [], failed = [], cfv = cfg.getRange(2, 1, 299, 21).getValues(), hist = ss.getSheetByName('_HISTORY'), pend = ss.getSheetByName('_PENDING');
  pick.forEach(function (key) {
    if (stop) return;
    var S = info[key], F = files[S.fi], lines = F.rows.filter(function (x, i) { return i > 0 && x[0] === S.id && x[1] === 'READY'; }), bad = [], ops = [];
    lines.forEach(function (x) {
      var sh = ss.getSheetByName(x[3]); if (!sh) { bad.push('tab not found: ' + x[3]); return; }
      var c = sh.getRange(x[4]), r0 = c.getRow(), col = c.getColumn(), outCell = sh.getRange(r0 + 1, col);
      var pw = String(sh.getRange(r0, 1).getDisplayValue()), outA = String(sh.getRange(r0 + 1, 1).getDisplayValue()), outLab = String(outCell.getDisplayValue());
      if (pw !== x[5] || outA !== 'OUT' || outLab !== x[6]) { bad.push(x[3] + ' ' + x[4] + ': box is ' + pw + ' / ' + outLab + ', expected ' + x[5] + ' / ' + x[6]); return; }
      var q = Number(x[7]); if (!(q > 0)) { bad.push(x[3] + ' ' + x[5] + ' / ' + x[6] + ': qty ' + x[7]); return; }
      ops.push({ sh: sh, cell: outCell, stockCell: c, q: q, stock: Number(c.getValue()) || 0, power: x[5], add: x[6], tab: x[3] });
    });
    if (bad.length) { failed.push(S.party + ':  ' + bad.slice(0, 4).join(' | ')); return; }
    var mode = 'new', pu = String(S.party).trim().toUpperCase();
    if (SAME_DAY_PARTIES.indexOf(pu) >= 0) {
      var chk = startSlipFor(pu, ''), today = Utilities.formatDate(new Date(), ss.getSpreadsheetTimeZone(), 'dd MMM');
      if (chk && chk.ok) cfg.getRange('Q3').setValue(NO_SLIP);   // no recent slip: it opened one, close it; a new one opens below
      if (chk && chk.recent) chk.recent.forEach(function (x) { if (mode === 'new' && x.day === today) mode = String(x.no); });
    }
    var res = startSlipFor(S.party, mode); if (!res || !res.ok) { failed.push(S.party + ': could not open slip ' + (res && res.msg)); return; }
    var adj = [], now = new Date();
    ops.forEach(function (o) {
      if (o.q <= o.stock) return;
      var diff = Math.round((o.q - o.stock) * 100) / 100, rng = '', block = '';
      cfv.forEach(function (r) { if (String(r[0]) !== o.tab) return; var ro = Number(r[20]) || 0;
        String(r[5]).split(',').forEach(function (a) { var R = o.sh.getRange(a.trim()); if (o.stockCell.getRow() >= R.getRow() && o.stockCell.getRow() <= R.getLastRow() && o.stockCell.getColumn() >= R.getColumn() && o.stockCell.getColumn() <= R.getLastColumn()) {
          rng = String(o.sh.getRange(o.stockCell.getRow(), o.stockCell.getColumn() + ro).getValue()); block = String(o.sh.getRange(R.getRow() - 2, R.getColumn()).getValue()); } }); });
      o.stockCell.setValue(o.q);
      hist.appendRow([now, o.tab, "'" + rng, "'" + o.power, "'" + o.add, 'IN', diff, o.stock, o.q, 'auto adjust', '', 'STOCK DIFFERENCE', o.stockCell.getA1Notation(), "'" + block]);
      adj.push(o.tab + ' ' + o.power + ' / ' + o.add + ': had ' + o.stock + ', gave ' + o.q + ' (+' + diff + ')');
    });
    ops.forEach(function (o) { o.cell.setValue(o.q); pend.appendRow([o.sh.getName(), o.cell.getA1Notation()]); });
    SpreadsheetApp.flush();
    var r0 = postWithLock_(ss);
    if (r0.errors.length) { stop = true; failed.push(S.party + ' (slip ' + res.no + ' left OPEN, yellow – fix, then Finish slip; other slips NOT done yet): ' + r0.errors.slice(0, 3).join(' | ')); return; }
    var sm = slipSummary_(ss, res.no);
    cfg.getRange('Q3').setValue(NO_SLIP);
    if (typeof ensureSlipRegister_ === 'function') ensureSlipRegister_(ss);
    var stamp = 'POSTED ' + Utilities.formatDate(now, ss.getSpreadsheetTimeZone(), 'dd-MM HH:mm') + ' slip ' + res.no;
    F.rows.forEach(function (x, i) { if (i > 0 && x[0] === S.id && x[1] === 'READY') x[1] = stamp; });
    F.dirty = true;
    done.push('Slip ' + res.no + '  ' + S.party + ':  ' + sm.lines + ' lines, ' + sm.prs + ' prs' + (adj.length ? '\n     ⚠️ adjusted: ' + adj.join('; ') : ''));
  });
  files.forEach(function (F) { if (!F.dirty) return;
    F.f.setContent(F.rows.map(function (x) { return x.map(csvq_).join(','); }).join('\n') + '\n');
    if (!F.rows.some(function (x, i) { return i > 0 && x[1] === 'READY'; })) F.f.setTrashed(true); });
  ui.alert('📥 Slips from Claude', (done.length ? '✅ POSTED and closed:\n' + done.join('\n') : '') + (failed.length ? '\n\n❌ NOT posted (tell Claude):\n' + failed.join('\n') : ''), ui.ButtonSet.OK);
}
