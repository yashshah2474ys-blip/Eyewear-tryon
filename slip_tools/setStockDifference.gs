var SD_ITEMS = [
 {
  "tab": "BIRD SV HC",
  "cell": "T206",
  "power": "+2.00",
  "add": "-4.50",
  "stock": 2.0,
  "rng": "-600 CYL CROSS",
  "block": "CROSS"
 },
 {
  "tab": "DARK CYL PG KT HC",
  "cell": "S46",
  "power": "-1.50",
  "add": "+2.50",
  "stock": 3.0,
  "rng": "200 CYL",
  "block": "×45"
 },
 {
  "tab": "ECO COMP KT HC (+)",
  "cell": "G162",
  "power": "+3.00 +1.00",
  "add": "+2.25",
  "stock": 9.0,
  "rng": "+3+1",
  "block": "×180"
 },
 {
  "tab": "MARCO CROSS KT HC",
  "cell": "Q40",
  "power": "+0.75 -1.00",
  "add": "+2.00",
  "stock": 2.0,
  "rng": "-200 CYL CROSS",
  "block": "×135"
 },
 {
  "tab": "ECO COMP KT HC (-)",
  "cell": "I176",
  "power": "-2.50 -1.50",
  "add": "+2.75",
  "stock": 18.5,
  "rng": "-3-2",
  "block": "×90"
 }
];
/* Raj Optical stock difference (27-28 Nov): set 5 cells to 0 and log in _HISTORY.
   Does NOT touch the SLIPS tab. Safe to run twice (skips a cell that is not at its expected stock). */
function setStockDifference() {
  var ss = SpreadsheetApp.getActive(), hist = ss.getSheetByName('_HISTORY'), now = new Date(), rows = [], msg = [];
  SD_ITEMS.forEach(function (it) {
    var c = ss.getSheetByName(it.tab).getRange(it.cell), cur = Number(c.getValue()) || 0;
    if (cur !== Number(it.stock)) { msg.push(it.tab + ' ' + it.cell + ' is ' + cur + ' (expected ' + it.stock + ') - NOT changed'); return; }
    c.setValue(0);
    rows.push([now, it.tab, "'" + it.rng, "'" + it.power, "'" + it.add, 'OUT', cur, cur, 0, 'stock difference', '', 'STOCK DIFFERENCE', it.cell, "'" + it.block]);
    msg.push(it.tab + ' ' + it.cell + ': ' + cur + ' -> 0');
  });
  if (rows.length) hist.getRange(hist.getLastRow() + 1, 1, rows.length, 14).setValues(rows);
  SpreadsheetApp.getUi().alert(msg.join('\n'));
}
