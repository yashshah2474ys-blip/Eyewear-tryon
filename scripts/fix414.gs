/* fix414: finish STOCK DIFFERENCE slip 414 – zero the last 23 CONNECT BRC PROG HMC boxes (762 prs). Run once. */
function fix414() {
  var ss = SpreadsheetApp.getActiveSpreadsheet(), ui = SpreadsheetApp.getUi(), T = 'CONNECT BRC PROG HMC';
  var L = [["I26",47,"+2.50"],["J26",27,"+2.75"],["K26",27,"+3.00"],["E28",10,"+1.50"],["F28",7,"+1.75"],["G28",27,"+2.00"],["H28",19,"+2.25"],["I28",127,"+2.50"],["J28",23,"+2.75"],["K28",30,"+3.00"],["E30",3,"+1.50"],["G30",4,"+2.00"],["H30",2,"+2.25"],["I30",16,"+2.50"],["J30",4,"+2.75"],["K30",7,"+3.00"],["E32",9,"+1.50"],["F32",19,"+1.75"],["G32",41,"+2.00"],["H32",57,"+2.25"],["I32",126,"+2.50"],["J32",20,"+2.75"],["K32",110,"+3.00"]];
  var lock = LockService.getDocumentLock(); lock.waitLock(30000);
  try {
    var sh = ss.getSheetByName(T), V = sh.getRange(1, 1, 33, 45).getValues(), bad = [], rows = [], now = new Date(), tot = 0;
    var h = ss.getSheetByName('_HISTORY'), hv = h.getRange(2, 1, h.getLastRow() - 1, 13).getValues();
    if (hv.some(function (r) { return Number(r[10]) === 414 && r[1] === T && r[12] === 'K32'; })) { ui.alert('Already done – nothing changed.'); return; }
    L.forEach(function (x) {
      var c = sh.getRange(x[0]), r = c.getRow(), col = c.getColumn(), stock = V[r - 1][col - 1], out = V[r][col - 1], lab = String(V[6][col - 1]);
      if (Number(stock) !== x[1] || Number(out) !== x[1] || lab !== x[2]) bad.push(x[0] + ': stock ' + stock + ', OUT box ' + out + ', label ' + lab + ' (expected ' + x[1] + ')');
      rows.push([now, T, "'" + V[r - 1][col - 1 + 30], "'" + V[r - 1][0], "'" + lab, 'OUT', x[1], x[1], 0, '', 414, 'STOCK DIFFERENCE', x[0], "'" + V[5][1]]);
      tot += x[1];
    });
    if (bad.length) { ui.alert('Sheet is different – NOTHING changed. Tell Claude:\n' + bad.slice(0, 8).join('\n')); return; }
    L.forEach(function (x) { var c = sh.getRange(x[0]); c.setValue(0); sh.getRange(c.getRow() + 1, c.getColumn()).setValue("'" + x[2]); });
    var at = h.getLastRow() + 1; if (h.getMaxRows() < at + rows.length + 5) h.insertRowsAfter(h.getMaxRows(), 200);
    h.getRange(at, 1, rows.length, 14).setValues(rows);
    var p = ss.getSheetByName('_PENDING');
    if (p && p.getLastRow() > 0) { var pv = p.getRange(1, 1, p.getLastRow(), 2).getValues().filter(function (r) { return r[0] && r[0] !== T; }); p.clearContents(); if (pv.length) p.getRange(1, 1, pv.length, 2).setValues(pv); }
    if (typeof ensureSlipRegister_ === 'function') ensureSlipRegister_(ss);
    ui.alert('✅ Slip 414 STOCK DIFFERENCE completed: ' + rows.length + ' lines, ' + tot + ' prs. CONNECT BRC PROG HMC is now 0.');
  } finally { lock.releaseLock(); }
}
