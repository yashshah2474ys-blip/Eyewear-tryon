# Slip work handover (read first in a new chat)

1. Read `slip_tools/RULEBOOK.txt` (same as Drive file "CLAUDE RULEBOOK v3").
2. Main sheet: Google Drive id `1MtG5CjqWFzG_Ho7WI1CSNh1NsY4Gd301JUj9ai8Utws` (EZRA STREET - MAIN GODOWN STOCK).
   Download as xlsx, use `slip_tools/find_cell.py` (`Book(xlsx).find(tab, power, add, block)`) to get cell + stock.
3. Batch file = CSV in Drive titled `CLAUDE SLIP <dd-mm> batchN`, columns:
   `slip_id,status,party,tab,cell,power,add,qty,note,slip` (status READY; slip = existing slip no. to add to, else blank = new slip).
   Owner loads with 📦 Stock → 📥 → A (loader v19f, `slip_tools/ClaudeInbox_f.gs`).
4. ONE batch file at a time. Verify every load in `_HISTORY` before making the next. Big loads (>80 lines) time out: split.
5. Every slip reply: match staff total, list given lines, end with "Staff missed: ..." (check stock for every not-given line).
6. Stock can only go DOWN through the loader (auto-adjusts up if given > stock). Put-backs/moves need a small Apps Script.
