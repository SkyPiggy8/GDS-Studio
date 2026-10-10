"""Persistent sample library. Geometry is deduplicated; occurrences never are.

Use a new Library connection in each process. WAL and explicit transactions
allow the gallery to remain readable while a worker imports samples.
"""
import hashlib
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from .matching import fingerprints, similarity


def json_text(value):return json.dumps(value,ensure_ascii=False,separators=(",",":"))


def file_hash(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(4*1024*1024),b""):h.update(block)
    return h.hexdigest()


class Library:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(str(self.path),timeout=30);self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL");self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        INSERT OR IGNORE INTO meta VALUES('schema','1');
        CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY, identity TEXT UNIQUE NOT NULL,
          path TEXT NOT NULL,kind TEXT NOT NULL,metadata TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS samples(id INTEGER PRIMARY KEY,name TEXT NOT NULL,
          layer INTEGER NOT NULL,datatype INTEGER NOT NULL,calibrated INTEGER NOT NULL,
          polygons TEXT NOT NULL,strict TEXT NOT NULL,congruent TEXT NOT NULL,same_shape TEXT NOT NULL,
          width REAL,height REAL,area REAL,components INTEGER,holes INTEGER,
          tags TEXT NOT NULL DEFAULT '',review TEXT NOT NULL DEFAULT 'draft',created TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(strict,layer,datatype,calibrated));
        CREATE INDEX IF NOT EXISTS sample_congruent ON samples(congruent);
        CREATE INDEX IF NOT EXISTS sample_same_shape ON samples(same_shape);
        CREATE TABLE IF NOT EXISTS occurrences(id INTEGER PRIMARY KEY,sample_id INTEGER NOT NULL REFERENCES samples(id),
          source_id INTEGER NOT NULL REFERENCES sources(id),identity TEXT NOT NULL,metadata TEXT NOT NULL,
          UNIQUE(sample_id,source_id,identity));
        ''')
        self.db.commit()
        if self.db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()[0]!="1":raise ValueError("不支持的样本库版本")

    def close(self):self.db.close()

    @contextmanager
    def transaction(self):
        try:
            self.db.execute("BEGIN IMMEDIATE");yield;self.db.commit()
        except BaseException:
            self.db.rollback();raise

    def source(self,identity,path,kind,metadata=None):
        self.db.execute("INSERT OR IGNORE INTO sources(identity,path,kind,metadata) VALUES(?,?,?,?)",(identity,str(path),kind,json_text(metadata or {})))
        return self.db.execute("SELECT id FROM sources WHERE identity=?",(identity,)).fetchone()[0]

    def add(self,polygons,name,layer,datatype,calibrated,source_id,occurrence):
        fp=fingerprints(polygons)
        cur=self.db.execute('''INSERT OR IGNORE INTO samples(name,layer,datatype,calibrated,polygons,strict,congruent,same_shape,width,height,area,components,holes)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(name,layer,datatype,int(calibrated),json_text(polygons),*[fp[k] for k in ("strict","congruent","same_shape","width","height","area","components","holes")]))
        added=cur.rowcount==1
        sample_id=self.db.execute("SELECT id FROM samples WHERE strict=? AND layer=? AND datatype=? AND calibrated=?",(fp["strict"],layer,datatype,int(calibrated))).fetchone()[0]
        key=hashlib.sha256(json_text(occurrence).encode()).hexdigest()
        self.db.execute("INSERT OR IGNORE INTO occurrences(sample_id,source_id,identity,metadata) VALUES(?,?,?,?)",(sample_id,source_id,key,json_text(occurrence)))
        return sample_id,added

    def count(self,query="",layer=None):
        clause,args=self._where(query,layer)
        return self.db.execute("SELECT count(*) FROM samples"+clause,args).fetchone()[0]

    def _where(self,query,layer):
        args=[];parts=[]
        if query:parts.append("(name LIKE ? OR tags LIKE ?)");args += [f"%{query}%"]*2
        if layer is not None:parts.append("layer=? AND datatype=?");args+=list(layer)
        return (" WHERE "+" AND ".join(parts) if parts else ""),args

    def list(self,query="",layer=None,offset=0,limit=80):
        clause,args=self._where(query,layer)
        return [dict(r) for r in self.db.execute("SELECT id,name,layer,datatype,calibrated,width,height,tags,review FROM samples"+clause+" ORDER BY layer,datatype,id LIMIT ? OFFSET ?",args+[limit,offset])]

    def layers(self):return [tuple(r) for r in self.db.execute("SELECT DISTINCT layer,datatype FROM samples ORDER BY layer,datatype")]

    def get(self,id,origins_limit=None):
        row=self.db.execute("SELECT * FROM samples WHERE id=?",(id,)).fetchone()
        if row is None:raise ValueError("样本不存在")
        result=dict(row);result["polygons"]=json.loads(result["polygons"])
        result["origin_count"]=self.db.execute("SELECT count(*) FROM occurrences WHERE sample_id=?",(id,)).fetchone()[0]
        result["origins"]=[{**dict(r),"metadata":json.loads(r["metadata"]),"source_metadata":json.loads(r["source_metadata"])} for r in self.db.execute('''SELECT o.metadata,s.path,s.kind,s.metadata AS source_metadata
          FROM occurrences o JOIN sources s ON s.id=o.source_id WHERE sample_id=? ORDER BY o.id LIMIT ?''',(id,-1 if origins_limit is None else origins_limit))]
        return result

    def update(self,id,name,tags,review):
        if review not in ("draft","reviewed"):raise ValueError("无效审核状态")
        self.db.execute("UPDATE samples SET name=?,tags=?,review=? WHERE id=?",(name,tags,review,id));self.db.commit()

    def matches(self,polygons,calibrated=True,exclude=None,limit=20,approximate=False):
        fp=fingerprints(polygons);results=[];seen=set()
        for mode,label in [("strict","尺寸一致"),("congruent","等尺寸旋转 / 镜像"),("same_shape","同形 · 忽略整体尺寸")]:
            if mode!="same_shape" and not calibrated:continue
            for r in self.db.execute(f"SELECT id,name,layer,datatype,calibrated FROM samples WHERE {mode}=? ORDER BY id LIMIT ?",(fp[mode],limit)):
                r=dict(r)
                if r["id"]==exclude or r["id"] in seen or (mode!="same_shape" and not r["calibrated"]):continue
                r.update(relation=label,score=1.0);results.append(r);seen.add(r["id"])
        if approximate:
            # Bounded shortlist by topology and fill ratio; never scan full geometry database.
            fill=fp["area"]/max(fp["width"]*fp["height"],1e-30)
            candidates=self.db.execute('''SELECT id,name,layer,datatype,calibrated,polygons FROM samples WHERE components=? AND holes=?
              ORDER BY ABS(area/(width*height)-?) LIMIT 80''',(fp["components"],fp["holes"],fill))
            near=[]
            for r in candidates:
                r=dict(r)
                if r["id"]==exclude or r["id"] in seen:continue
                score=similarity(polygons,json.loads(r.pop("polygons")))
                if score>=.5:r.update(relation="相似候选 · 非重复判定",score=score);near.append(r)
            results+=sorted(near,key=lambda r:-r["score"])
        return results[:limit]


def add_document(library,document,identity,path="画布",kind="project",metadata=None):
    added=duplicate=0;ids=[]
    with library.transaction():
        source=library.source(identity,path,kind,metadata)
        for shape in document.shapes:
            calibrated=shape.metadata.get("calibrated",True)
            for layer,datatype,polys in shape.entries():
                from .geometry import bounds
                id,new=library.add(polys,shape.name,layer,datatype,calibrated,source,{"shape_id":shape.id,"shape_metadata":shape.metadata,"method":"editor_object","bounds_nm":list(bounds(polys))});ids.append(id)
                added+=int(new);duplicate+=int(not new)
    return {"added":added,"duplicates":duplicate,"ids":ids}
