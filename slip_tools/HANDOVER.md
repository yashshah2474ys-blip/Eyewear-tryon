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
7. Report format: table "paper line -> entered as (tab, axis block, cell) -> prs". Always write the AXIS for cyl/comp lines.
   Don't flag short stock (loader auto-adjusts). Ask only real doubts; check a lens exists before asking.
8. Same-day slip parties (put slip = their slip no. today): RIAZ, SUNNY, MUNNA, ASGAR, YUSUF, MOIDUL. Ignore sub-party names on their papers.
   Every other paper = new slip. A new paper for a party is a NEW slip, never a correction of an old one unless the owner says so.
9. Timeout: if the loader says "Exceeded maximum execution time", download the sheet, see which lines posted, trash the file,
   upload only the remaining lines (slip = the slip number already opened).

## State at end of 26-11 (chat 1)
- Last posted: batch66 -> slips 510 (Yusuf) and 517 (Sudershan Malda). All of 26-11 verified up to slip 517.
- Today's same-day slips: SUNNY 490, MUNNA 500, RIAZ 504, MOIDUL 505, YUSUF 510.
- Nothing pending. Next job: RAJ RANCHI, 13 pages mixed items -> read 3-4 pages at a time, hold, match packing slip,
  then upload in parts of ~60 lines (part 1 = new slip, later parts slip = that number). Next batch number: batch67.

## State 26-11 (chat 2) - RAJ OPTICAL (Raj Ranchi, 13 pages)
- Reading done and matched with packing slip (312 prs = 266 blue + 44 red Paul + held cross KT line).
- batch67 part 1 (60 lines, 165.5 prs, new slip) uploaded to Drive as "CLAUDE SLIP 26-11 batch67". Verify in _HISTORY.
- Part 2 = slip_tools/raj_26-11/batch67_part2.csv (35 lines, 100.5 prs) -> set slip column to part-1 slip no.
  + MARCO CROSS KT HC Q40 qty 2 already added to part2 file.
- Holds: p3 BC KT +1.00/+0.75 x180 add 2.00; p9 BC Prog +1.50/+0.50 x180 add 2.00 (owner to confirm).
- Stock differences (end): p10 MARCO CROSS KT HC Q40 (2 prs, after giving 2); p3 BIRD T206 +2.00/-4.50; p7 DARK CYL PG KT S46 -1.50 x45 add 2.50; p7 ECO COMP KT (+) G162 +3.00/+1.00 add 2.25; p11 ECO COMP KT (-) I176 -2.50/-1.50 add 2.75.
