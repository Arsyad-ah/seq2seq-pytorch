from model import *
from utils import *
# from evaluate import *

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
    enc = encoder(len(src_vocab))
    dec = decoder(len(tgt_vocab))
    enc_optim = torch.optim.Adam(enc.parameters(), lr = LEARNING_RATE)
    dec_optim = torch.optim.Adam(dec.parameters(), lr = LEARNING_RATE)
    epoch = load_checkpoint(sys.argv[1], enc, dec) if isfile(sys.argv[1]) else 0
    filename = re.sub("\.epoch[0-9]+$", "", sys.argv[1])
    print(enc)
    print(dec)
    print("training model...")
    for ei in range(epoch + 1, epoch + num_epochs + 1):
        ii = 0
        loss_sum = 0
        timer = time()
        for x, y in data:
            ii += 1
            loss = 0
            enc.zero_grad()
            dec.zero_grad()
            mask = maskset(x)
            enc_out = enc(x, mask)
            dec_in = LongTensor([SOS_IDX] * BATCH_SIZE).unsqueeze(1)
            dec.hidden = enc.hidden
            if dec.feed_input:
                dec.attn.hidden = zeros(BATCH_SIZE, 1, HIDDEN_SIZE)
            for t in range(y.size(1)):
                dec_out = dec(dec_in, enc_out, t, mask)
                loss += F.nll_loss(dec_out, y[:, t], ignore_index = PAD_IDX, reduction = "sum")
                dec_in = y[:, t].unsqueeze(1) # teacher forcing
            loss /= y.data.gt(0).sum().float() # divide by the number of unpadded tokens
            loss.backward()
            enc_optim.step()
            dec_optim.step()
            loss = loss.item()
            loss_sum += loss
            # print("epoch = %d, iteration = %d, loss = %f" % (ei, ii, loss))
        timer = time() - timer
        loss_sum /= len(data)
        if ei % SAVE_EVERY and ei != epoch + num_epochs:
            save_checkpoint("", None, None, ei, loss_sum, timer)
        else:
            save_checkpoint(filename, enc, dec, ei, loss_sum, timer)

if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit("Usage: %s model vocab.src vocab.tgt training_data num_epoch" % sys.argv[0])
    train()
