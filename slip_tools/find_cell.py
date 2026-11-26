import openpyxl,re,sys,json
from openpyxl.utils import column_index_from_string as ci, get_column_letter as cl
class Book:
  def __init__(s,f):
    s.wb=openpyxl.load_workbook(f,read_only=True,data_only=True); s.cache={}
    s.cfg={r[0]:r for r in s.wb['_CONFIG'].iter_rows(min_row=2,max_row=300,max_col=21,values_only=True) if r and r[0]}
  def grid(s,t):
    if t not in s.cache: s.cache[t]=[list(r)+[None]*120 for r in s.wb[t].iter_rows(max_row=400,max_col=120,values_only=True)]
    return s.cache[t]
  def find(s,t,power,add,block=None):
    V=s.grid(t); out=[]; ro=int(s.cfg[t][20] or 0)
    for a in str(s.cfg[t][5]).split(','):
      m=re.match(r'([A-Z]+)(\d+):([A-Z]+)(\d+)',a.strip()); c1,r1,c2,r2=ci(m[1]),int(m[2]),ci(m[3]),int(m[4])
      blk=str(V[r1-3][c1-1])
      for r in range(r1,r2+1,2):
        if str(V[r-1][0])!=power: continue
        for c in range(c1,c2+1):
          if str(V[r1-2][c-1])==add and (block is None or block in blk):
            out.append(dict(tab=t,cell=cl(c)+str(r),power=power,add=str(V[r][c-1]),stock=V[r-1][c-1],block=blk,rng=V[r-1][c-1+ro]))
    return out
