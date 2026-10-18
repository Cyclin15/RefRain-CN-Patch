# -*- coding: utf-8 -*-
"""Parser/rebuilder for .NET .resources v2 binary blobs (System.Resources.ResourceReader format).

Empirically reverse-engineered layout (all offsets relative to blob start):
  [magic u32 = 0xBEEFCACE][headerVersion u32][headerSize u32]
  [readerType lenstr][resourceSetType lenstr]        (lenstr = 7bit-len + UTF-8)
  [version i32 = 2][numResources i32][numTypes i32]
  [typeNames: numTypes x lenstr]
  ["PAD" + zeros up to 8-alignment of (headerSize-relative? -> blob start)]
  [nameHashes: numResources x u32]
  [namePositions: numResources x i32]   (relative to nameBase)
  [dataSectionOffset i32]               (absolute in blob)
  name entries at nameBase = right after that i32:
      [7bit namelen][UTF-16LE name][i32 dataOffset]   (dataOffset relative to data section)
  data entries at dsoff + dataOffset:
      [7bit typeCode][value]
      typeCode 1 = String: value = [7bit len][UTF-8 bytes]
      other types: raw bytes follow (length inferred from next entry / type semantics)
"""
import struct

MAGIC = b"\xce\xca\xef\xbe"

def read7(b, p):
    v = 0; s = 0
    while True:
        x = b[p]; p += 1
        v |= (x & 0x7f) << s
        if not (x & 0x80): return v, p
        s += 7

def write7(v):
    out = bytearray()
    while True:
        x = v & 0x7f; v >>= 7
        if v: out.append(x | 0x80)
        else: out.append(x); return bytes(out)

def read_lenstr(b, p):
    n, p = read7(b, p)
    return b[p:p+n].decode("utf-8"), p+n

class Entry:
    __slots__ = ("name", "hash", "pos", "name_off", "name_len", "data_off", "type_code", "value", "raw_span")

class ResFile:
    def __init__(self, data):
        self.data = data
        assert data[:4] == MAGIC, "bad magic"
        self.hver, self.hsize = struct.unpack_from("<II", data, 4)
        p = 12
        self.reader_type, p = read_lenstr(data, p)
        self.set_type, p = read_lenstr(data, p)
        assert p == 12 + self.hsize, f"header size mismatch {p} vs {12+self.hsize}"
        self.version, self.nres, self.ntypes = struct.unpack_from("<iii", data, p)
        p += 12
        self.type_names = []
        for _ in range(self.ntypes):
            s, p = read_lenstr(data, p)
            self.type_names.append(s)
        # PAD to 8-alignment relative to blob start, then hashes
        q = (p + 7) & ~7
        assert data[p:q] == b"P" + b"A"*(q-p-1) or all(c in b"PAD" for c in data[p:q]), "pad?"
        hp = q
        self.hash_pos = hp
        self.positions_pos = hp + 4*self.nres
        self.dsoff_pos = self.positions_pos + 4*self.nres
        self.dsoff, = struct.unpack_from("<i", data, self.dsoff_pos)
        self.name_base = self.dsoff_pos + 4
        hashes = struct.unpack_from("<%dI" % self.nres, data, hp)
        positions = struct.unpack_from("<%di" % self.nres, data, self.positions_pos)
        # name entries sorted by position
        self.entries = []
        spans = sorted(zip(positions, range(self.nres)))
        prev_end = None
        for pos, idx in spans:
            e = Entry()
            e.pos = pos
            e.hash = hashes[idx]
            np_ = self.name_base + pos
            nlen, np2 = read7(data, np_)  # 7-bit length = BYTE length of UTF-16LE name
            e.name = data[np2:np2+nlen].decode("utf-16-le")
            e.name_off = np_
            e.name_len = np2 + nlen - np_
            tp = np2 + nlen
            e.data_off, = struct.unpack_from("<i", data, tp)
            # data entry
            dp = self.dsoff + e.data_off
            tc, dp2 = read7(data, dp)
            e.type_code = tc
            if tc == 1:  # String
                vlen, dp3 = read7(data, dp2)
                e.value = data[dp3:dp3+vlen].decode("utf-8")
                e.raw_span = (dp, dp3+vlen)
            else:
                e.value = None  # raw blob, span filled by finalize pass
                e.raw_span = (dp, None)
            self.entries.append(e)
        self.entries.sort(key=lambda e: e.pos)
        # fill raw spans of non-string entries: end = next entry's start (data section
        # entries are contiguous in dataOffset order)
        byd = sorted(self.entries, key=lambda e: e.data_off)
        for i, e in enumerate(byd):
            if e.raw_span[1] is None:
                end = byd[i+1].data_off if i+1 < len(byd) else None
                if end is None:
                    # last entry: ends at blob end? use heuristics below
                    e.raw_span = (e.raw_span[0], len(data))
                else:
                    e.raw_span = (e.raw_span[0], self.dsoff + end)
        self.byd = byd

    def get(self, name):
        for e in self.entries:
            if e.name == name: return e
        return None

    def dump(self):
        print(f"  hver={self.hver} hsize={self.hsize} version={self.version} nres={self.nres} ntypes={self.ntypes} dsoff={self.dsoff} name_base={self.name_base} bloblen={len(self.data)}")
        for e in self.entries:
            if e.type_code == 1:
                v = e.value
                if len(v) > 80: v = v[:80] + "..."
                print(f"  [{e.pos:5d}] {e.name} = {v!r}")
            else:
                print(f"  [{e.pos:5d}] {e.name} = <typeCode {e.type_code:#x} {e.raw_span[1]-e.raw_span[0]}B raw>")

def rebuild(orig: ResFile, string_map, orig_blob_len):
    """Rebuild blob with same header/hashes/positions/names, replacing String values
    via string_map {name: new_value}. Returns bytes padded/truncated check to orig_blob_len.
    Non-string entries copied raw. Raises if new blob > orig_blob_len."""
    data = bytearray(orig.data)
    # build new data section in original dataOffset order
    new_data = bytearray()
    new_off = {}
    for e in orig.byd:
        new_off[e.name] = len(new_data)
        if e.type_code == 1:
            v = string_map.get(e.name, e.value)
            vb = v.encode("utf-8")
            new_data += write7(1) + write7(len(vb)) + vb
        else:
            s, t = e.raw_span
            new_data += orig.data[s:t]
    name_end = orig.dsoff  # data section starts right after name section
    out = bytearray(orig.data[:name_end])
    assert len(out) == orig.dsoff, "name section size changed?"
    out += new_data
    if len(out) > orig_blob_len:
        raise ValueError(f"overflow: {len(out)} > {orig_blob_len}")
    out += b"\x00" * (orig_blob_len - len(out))
    # patch trailers (dataOffset per name, positions unchanged because names unchanged)
    for e in orig.entries:
        struct.pack_into("<i", out, e.name_off + e.name_len, new_off[e.name])
    return bytes(out)
