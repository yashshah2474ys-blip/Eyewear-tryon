/* fixAlokMove: Alok 403 put back 5 at (-) x135 -2.50 -0.50 add 2.50, then move 9 to -3.00 -0.50 add 2.50. Run once. */
function fixAlokMove() {
  var ss = SpreadsheetApp.getActiveSpreadsheet(), P = PropertiesService.getDocumentProperties(), T = 'ECO COMP KT HC (-)';
  function say(m) { Logger.log(m); ss.toast(m, 'fixAlokMove', 60); }
  if (P.getProperty('FIX_ALOK_MOVE')) { say('Already done before – nothing changed.'); return; }
  var lock = LockService.getDocumentLock(); lock.waitLock(30000);
  try {
    var sh = ss.getSheetByName(T), a = sh.getRange('AD170'), b = sh.getRange('AD186');
    var pa = sh.getRange('A170').getDisplayValue(), pb = sh.getRange('A186').getDisplayValue(), la = sh.getRange('AD171').getDisplayValue(), lb = sh.getRange('AD187').getDisplayValue();
    var va = Number(a.getValue()), vb = Number(b.getValue());
    if (pa !== '-2.50 -0.50' || pb !== '-3.00 -0.50' || la !== '+2.50' || lb !== '+2.50' || va !== 4 || vb !== 25) { say('Sheet is different – NOTHING changed. Tell Claude: ' + pa + ' ' + va + ' / ' + pb + ' ' + vb); return; }
    var h = ss.getSheetByName('_HISTORY'), hv = h.getRange(2, 11, h.getLastRow() - 1, 1).getValues(), mx = 0;
    hv.forEach(function (r) { var k = Number(r[0]); if (k > mx) mx = k; });
    var sd = mx + 1, now = new Date(), rng = String(sh.getRange(170, 102).getDisplayValue()), rngb = String(sh.getRange(186, 102).getDisplayValue());
    var rows = [
      [now, T, "'" + rng, "'-2.50 -0.50", "'+2.50", 'IN', 5, 4, 9, 'put back', 403, 'ALOK PURSHANTAM', 'AD170', "'×135"],
      [now, T, "'" + rng, "'-2.50 -0.50", "'+2.50", 'OUT', 9, 9, 0, 'moved to -3.00 -0.50', sd, 'STOCK DIFFERENCE', 'AD170', "'×135"],
      [now, T, "'" + rngb, "'-3.00 -0.50", "'+2.50", 'IN', 9, 25, 34, 'moved from -2.50 -0.50', sd, 'STOCK DIFFERENCE', 'AD186', "'×135"]];
    a.setValue(0); b.setValue(34);
    h.getRange(h.getLastRow() + 1, 1, rows.length, 14).setValues(rows);
    P.setProperty('FIX_ALOK_MOVE', '1');
    if (typeof ensureSlipRegister_ === 'function') ensureSlipRegister_(ss);
    say('✅ Alok 403: 5 put back. Slip ' + sd + ' STOCK DIFFERENCE: 9 moved. -2.50 -0.50 = 0, -3.00 -0.50 = 34.');
  } finally { lock.releaseLock(); }
}
