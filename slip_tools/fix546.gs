/* One-time fix for slip 546 (SUPER/ARIF TATA), 27-11.
   Removes 2 wrong lines from _HISTORY and puts the stock back. Safe to run twice. */
function fix546() {
  var ss = SpreadsheetApp.getActive(), msg = [];
  // 1) put stock back (only if not already done)
  var a = ss.getSheetByName('MARCO COMP BRC KT HMC (+)').getRange('G42');
  if (Number(a.getValue()) === 36) { a.setValue(37); msg.push('G42 Marco Comp BRC KT +1.00/+0.50 add 2.25: 36 -> 37'); }
  else msg.push('G42 is ' + a.getValue() + ' (not changed)');
  var b = ss.getSheetByName('DARK COMP PG KT HC (+)').getRange('G48');
  if (Number(b.getValue()) === 12) { b.setValue(19); msg.push('G48 Dark Comp PG KT +1.00/+1.50 add 2.25: 12 -> 19'); }
  else msg.push('G48 is ' + b.getValue() + ' (not changed)');
  // 2) delete the 2 wrong slip lines from _HISTORY
  var h = ss.getSheetByName('_HISTORY'), v = h.getDataRange().getValues(), del = [];
  for (var i = v.length - 1; i >= 1; i--) {
    var r = v[i];
    if (Number(r[10]) !== 546 || r[5] !== 'OUT') continue;
    if ((r[1] === 'DARK COMP PG KT HC (+)' && r[12] === 'G48' && Number(r[6]) === 7) ||
        (r[1] === 'MARCO COMP BRC KT HMC (+)' && r[12] === 'G42' && Number(r[6]) === 1)) { h.deleteRow(i + 1); del.push(r[1] + ' ' + r[12]); }
  }
  msg.push('Deleted from _HISTORY: ' + (del.length ? del.join(', ') : 'nothing (already done)'));
  // 3) fix the slip register totals
  v = h.getDataRange().getValues(); var n = 0, p = 0;
  v.forEach(function (r, i) { if (i && Number(r[10]) === 546 && r[5] === 'OUT') { n++; p += Number(r[6]) || 0; } });
  var s = ss.getSheetByName('📒 SLIPS'), sv = s.getDataRange().getValues();
  for (var j = 0; j < sv.length; j++) if (Number(sv[j][0]) === 546) { s.getRange(j + 1, 4).setValue(n); s.getRange(j + 1, 5).setValue(p); }
  msg.push('Slip 546 now: ' + n + ' lines, ' + p + ' prs');
  SpreadsheetApp.getUi().alert(msg.join('\n'));
}
