import sys
import re
from time import time
from os.path import isfile
from parameters import *
from collections import defaultdict

def normalize(x):
    # x = re.sub("[^ ,.?!a-zA-Z0-9\u3131-\u318E\uAC00-\uD7A3]+", " ", x)
    x = re.sub("(?=[,.?!])", " ", x)
    x = re.sub("\s+", " ", x)
    x = re.sub("^ | $", "", x)
    x = x.lower()
    return x

def tokenize(x, norm = True):
    if norm:
        x = normalize(x)
    if UNIT == "char":
        return re.sub(" ", "", x)
    if UNIT in ("word", "sent"):
        return x.split(" ")

def save_data(filename, data):
    fo = open(filename, "w")
    for seq in data:
        fo.write(" ".join(seq[0]) + "\t" + " ".join(seq[1]) + "\n")
    fo.close()

def load_tkn_to_idx(filename):
    print("loading %s" % filename)
    tkn_to_idx = {}
    fo = open(filename)
    for line in fo:
        line = line[:-1]
        tkn_to_idx[line] = len(tkn_to_idx)
    fo.close()
    return tkn_to_idx

def load_idx_to_tkn(filename):
    print("loading %s" % filename)
    idx_to_tkn = []
    fo = open(filename)
    for line in fo:
        line = line[:-1]
        idx_to_tkn.append(line)
    fo.close()
    return idx_to_tkn

def save_tkn_to_idx(filename, tkn_to_idx):
    fo = open(filename, "w")
    for tkn, _ in sorted(tkn_to_idx.items(), key = lambda x: x[1]):
        fo.write("%s\n" % tkn)
    fo.close()

def load_checkpoint(filename, model = None):
    print("loading %s" % filename)
    checkpoint = torch.load(filename)
    if model:
        model.enc.load_state_dict(checkpoint["enc_state_dict"])
        model.dec.load_state_dict(checkpoint["dec_state_dict"])
    epoch = checkpoint["epoch"]
    loss = checkpoint["loss"]
    print("saved model: epoch = %d, loss = %f" % (checkpoint["epoch"], checkpoint["loss"]))
    return epoch

def save_checkpoint(filename, model, epoch, loss, time):
    print("epoch = %d, loss = %f, time = %f" % (epoch, loss, time))
    if filename and model:
        print("saving %s" % filename)
        checkpoint = {}
        checkpoint["enc_state_dict"] = model.enc.state_dict()
        checkpoint["dec_state_dict"] = model.dec.state_dict()
        checkpoint["epoch"] = epoch
        checkpoint["loss"] = loss
        torch.save(checkpoint, filename + ".epoch%d" % epoch)
        print("saved model at epoch %d" % epoch)

def cudify(f):
    return lambda *x: f(*x).cuda() if CUDA else f(*x)

Tensor = cudify(torch.Tensor)
LongTensor = cudify(torch.LongTensor)
zeros = cudify(torch.zeros)

class dataset():
    def __init__(self):
        self.idx = [] # input index
        self.x0 = [[]] # raw input
        self.x1 = [[]] # tokenized input
        self.xc = [[]] # indexed input, character-level
        self.xw = [[]] # indexed input, word-level
        self.y0 = [[]] # actual output
        self.y1 = None # predicted output
        self.prob = None # probabilities
        self.heatmap = None

    def append_item(self, idx = -1, x0 = None, x1 = None, xc = None, xw = None, y0 = None):
        if idx >= 0 : self.idx.append(idx)
        if x0: self.x0[-1].append(x0)
        if x1: self.x1[-1].append(x1)
        if xc: self.xc[-1].append(xc)
        if xw: self.xw[-1].append(xw)
        if y0: self.y0[-1].extend(y0)

    def append_row(self):
        self.x0.append([])
        self.x1.append([])
        self.xc.append([])
        self.xw.append([])
        self.y0.append([])

    def strip(self):
        while len(self.xw[-1]) == 0:
            self.x0.pop()
            self.x1.pop()
            self.xc.pop()
            self.xw.pop()
            self.y0.pop()

    def sort(self):
        if not len(self.idx):
            self.idx = list(range(len(self.x0)))
        self.idx.sort(key = lambda x: -len(self.xw[x] if HRE else self.xw[x][0]))
        self.x1 = [self.x1[i] for i in self.idx]
        self.xc = [self.xc[i] for i in self.idx]
        self.xw = [self.xw[i] for i in self.idx]

    def unsort(self):
        idx = sorted(range(len(self.idx)), key = lambda x: self.idx[x])
        self.idx = list(range(len(self.x0)))
        self.x1 = [self.x1[i] for i in idx]
        self.xc = [self.xc[i] for i in idx]
        self.xw = [self.xw[i] for i in idx]
        self.y1 = [self.y1[i] for i in idx]
        self.prob = [self.prob[i] for i in idx]
        self.heatmap = [self.heatmap[i] for i in idx]

    def split(self): # split into batches
        self.y1 = [[] for _ in self.y0]
        self.prob = [0 for _ in self.y0]
        self.heatmap = [[] for _ in self.y0]
        for i in range(0, len(self.y0), BATCH_SIZE):
            j = i + BATCH_SIZE
            y0 = self.y0[i:j]
            y0_lens = [len(x) for x in self.xw[i:j]] if HRE else None
            y1 = self.y1[i:j]
            p1 = self.prob[i:j]
            h1 = self.heatmap[i:j]
            if HRE:
                x0 = [list(x) for x in self.x0[i:j] for x in x]
                x1 = [list(x) for x in self.x1[i:j] for x in x]
                xc = [list(x) for x in self.xc[i:j] for x in x]
                xw = [list(x) for x in self.xw[i:j] for x in x]
            else:
                x0 = [list(*x) for x in self.x0[i:j]]
                x1 = [list(*x) for x in self.x1[i:j]]
                xc = [list(*x) for x in self.xc[i:j]]
                xw = [list(*x) for x in self.xw[i:j]]
            yield x0, x1, xc, xw, y0, y0_lens, y1, p1, h1

    def tensor(self, bc, bw, _sos = False, _eos = False, doc_lens = None):
        sos, eos, pad = [SOS_IDX], [EOS_IDX], [PAD_IDX]
        if doc_lens:
            d_len = max(doc_lens) # doc_len (Ld)
            i, _bc, _bw = 0, [], []
            for j in doc_lens:
                _bc.extend(bc[i:i + j] + [[pad]] * (d_len - j))
                _bw.extend(bw[i:i + j] + [pad] * (d_len - j))
                i += j
            bc, bw = _bc, _bw
        if bw:
            s_len = max(map(len, bw)) # sent_len (Ls)
            bw = [sos * _sos + x + eos * _eos + pad * (s_len - len(x)) for x in bw]
            bw = LongTensor(bw) # [B * Ld, Ls]
        if bc:
            w_len = max(max(map(len, x)) for x in bc) # word_len (Lw)
            w_pad = [pad * (w_len + 2)]
            bc = [[sos + w + eos + pad * (w_len - len(w)) for w in x] for x in bc]
            bc = [w_pad * _sos + x + w_pad * (s_len - len(x) + _eos) for x in bc]
            bc = LongTensor(bc) # [B * Ld, Ls, Lw]
        return bc, bw

def batchify(bxc, bxw, sos = False, eos = False, minlen = 0):
    bxw_len = max(minlen, max(len(x) for x in bxw))
    if bxc:
        bxc_len = max(minlen, max(len(w) for x in bxc for w in x))
        pad = [[PAD_IDX] * (bxc_len + 2)]
        bxc = [[[SOS_IDX, *w, EOS_IDX, *[PAD_IDX] * (bxc_len - len(w))] for w in x] for x in bxc]
        bxc = [(pad if sos else []) + x + (pad * (bxw_len - len(x) + eos)) for x in bxc]
        bxc = LongTensor(bxc)
    sos = [SOS_IDX] if sos else []
    eos = [EOS_IDX] if eos else []
    bxw = [sos + list(x) + eos + [PAD_IDX] * (bxw_len - len(x)) for x in bxw]
    return bxc, LongTensor(bxw)

def maskset(x):
    mask = x.eq(PAD_IDX)
    return (mask, x.size(1) - mask.sum(1)) # tuple of mask and lengths

def mat2csv(m, ch = True, rh = False, nd = 4, delim ="\t"):
    f = "%%.%df" % nd
    if ch: # column header
        csv = delim.join([x for x in m[0]]) + "\n" # source sequence
    for row in m[ch:]:
        if rh: # row header
            csv += str(row[0]) + delim # target sequence
        csv += delim.join([f % x for x in row[rh:]]) + "\n"
    return csv

def f1(p, r):
    return 2 * p * r / (p + r) if p + r else 0
