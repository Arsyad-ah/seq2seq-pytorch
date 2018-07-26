import sys
import re
import time
from model import *
from utils import *
from os.path import isfile

def load_data():
    data = []
    src_batch = []
    tgt_batch = []
    src_batch_len = 0
    tgt_batch_len = 0
    print("loading data...")
    src_vocab = load_vocab(sys.argv[2], "src")
    tgt_vocab = load_vocab(sys.argv[3], "tgt")
    fo = open(sys.argv[4], "r")
    for line in fo:
        line = line.strip()
        src, tgt = line.split("\t")
        src = [int(i) for i in src.split(" ")] + [EOS_IDX]
        tgt = [int(i) for i in tgt.split(" ")] + [EOS_IDX]
        # src.reverse() # reversing source sequence
        if len(src) > src_batch_len:
            src_batch_len = len(src)
        if len(tgt) > tgt_batch_len:
            tgt_batch_len = len(tgt)
        src_batch.append(src)
        tgt_batch.append(tgt)
        if len(src_batch) == BATCH_SIZE:
            for seq in src_batch:
                seq.extend([PAD_IDX] * (src_batch_len - len(seq)))
            for seq in tgt_batch:
                seq.extend([PAD_IDX] * (tgt_batch_len - len(seq)))
            data.append((LongTensor(src_batch), LongTensor(tgt_batch)))
            src_batch = []
            tgt_batch = []
            src_batch_len = 0
            tgt_batch_len = 0
    fo.close()
    print("data size: %d" % (len(data) * BATCH_SIZE))
    print("batch size: %d" % BATCH_SIZE)
    return data, src_vocab, tgt_vocab

def train():
    print("cuda: %s" % CUDA)
    num_epochs = int(sys.argv[5])
    data, src_vocab, tgt_vocab = load_data()
    if VERBOSE:
        src_itow = [w for w, _ in sorted(src_vocab.items(), key = lambda x: x[1])]
        tgt_itow = [w for w, _ in sorted(tgt_vocab.items(), key = lambda x: x[1])]
    enc = encoder(len(src_vocab))
    dec = decoder(len(tgt_vocab))
    enc_optim = torch.optim.SGD(enc.parameters(), lr = LEARNING_RATE, weight_decay = WEIGHT_DECAY)
    dec_optim = torch.optim.SGD(dec.parameters(), lr = LEARNING_RATE, weight_decay = WEIGHT_DECAY)
    epoch = load_checkpoint(sys.argv[1], enc, dec) if isfile(sys.argv[1]) else 0
    filename = re.sub("\.epoch[0-9]+$", "", sys.argv[1])
    print(enc)
    print(dec)
    print("training model...")
    for ei in range(epoch + 1, epoch + num_epochs + 1):
        loss_sum = 0
        timer = time.time()
        for x, y in data:
            loss = 0
            x_mask = maskset(x)
            y_mask = maskset(y)
            enc.zero_grad()
            dec.zero_grad()
            memory = enc(x, x_mask)
            print(x.size())
            exit()
        timer = time.time() - timer
        loss_sum /= len(data)
        if ei % SAVE_EVERY and ei != epoch + num_epochs:
            save_checkpoint("", "", "", ei, loss_sum, timer)
        else:
            if VERBOSE:
                for x, y in zip(x, pred):
                    print(" ".join([src_itow[scalar(i)] for i in x if scalar(i) != PAD_IDX]))
                    print(" ".join([tgt_itow[i] for i in y if i != PAD_IDX]))
            save_checkpoint(filename, enc, dec, ei, loss_sum, timer)

if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit("Usage: %s model vocab.src vocab.tgt training_data num_epoch" % sys.argv[0])
    train()
