/* fixDada511: Dada slip 511 – 40 prs plano were posted on MARCO PG BRC HMC (green) but given from MARCO PG BRC BLUE HMC. Put 40 back on green, take 40 from blue. Run once. */
function fixDada511() {
  var ss = SpreadsheetApp.getActiveSpreadsheet(), P = PropertiesService.getDocumentProperties();
  function say(m) { Logger.log(m); ss.toast(m, 'fixDada511', 60); }
  if (P.getProperty('FIX_DADA_511')) { say('Already done before – nothing changed.'); return; }
  var lock = LockService.getDocumentLock(); lock.waitLock(30000);
  try {
    var G = 'MARCO PG BRC HMC', B = 'MARCO PG BRC BLUE HMC';
    var g = ss.getSheetByName(G).getRange('B8'), b = ss.getSheetByName(B).getRange('B8');
    var vg = Number(g.getValue()), vb = Number(b.getValue());
    if (vg !== 3851 || vb !== 1908) { say('Sheet is different – NOTHING changed. Tell Claude: green ' + vg + ' / blue ' + vb); return; }
    var h = ss.getSheetByName('_HISTORY'), now = new Date();
    var rows = [
      [now, G, "'-6-2", "'0.00", "'0.00", 'OUT', -40, 3851, 3891, 'put back - wrong lens', 511, 'DADA', 'B8', "'MINUS"],
      [now, B, "'-6-2", "'0.00", "'0.00", 'OUT', 40, 1908, 1868, 'correct lens', 511, 'DADA', 'B8', "'MINUS"]];
    g.setValue(3891); b.setValue(1868);
    h.getRange(h.getLastRow() + 1, 1, rows.length, 14).setValues(rows);
    P.setProperty('FIX_DADA_511', '1');
    if (typeof ensureSlipRegister_ === 'function') ensureSlipRegister_(ss);
    say('✅ Dada 511: 40 put back on PG BRC green (3891), 40 taken from PG BRC Blue (1868). Slip total still 40.');
  } finally { lock.releaseLock(); }
}
