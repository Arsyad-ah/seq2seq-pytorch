from utils import *
from embedding import embed

class ptrnet(nn.Module): # pointer networks
    def __init__(self, char_vocab_size, word_vocab_size):
        super().__init__()

        # architecture
        self.enc = encoder(char_vocab_size, word_vocab_size)
        self.dec = decoder(char_vocab_size, word_vocab_size)
        self = self.cuda() if CUDA else self

    def forward(self, xc, xw, y0): # for training
        b = y0.size(0) # batch size
        loss = 0
        self.zero_grad()
        mask = None if HRE else maskset(xw) # TODO
        enc_out = self.enc(b, xc, xw, mask)
        yc = LongTensor([[[SOS_IDX]]] * b)
        yw = LongTensor([[SOS_IDX]] * b)
        self.dec.hidden = self.enc.hidden
        for t in range(y0.size(1)):
            dec_out = self.dec(yc, yw, enc_out, t, mask)
            yw = y0[:, t] - 1 # teacher forcing
            loss += F.nll_loss(dec_out, yw, ignore_index = PAD_IDX - 1)
            yc = torch.cat([xc[i, j] for i, j in enumerate(yw)]).view(b, 1, -1)
            yw = torch.cat([xw[i, j].view(1, 1) for i, j in enumerate(yw)])
        loss /= y0.size(1) # divide by senquence length
        # loss /= y0.gt(0).sum().float() # divide by the number of unpadded tokens
        return loss

    def decode(self, xc, xw): # for inference
        pass

class encoder(nn.Module):
    def __init__(self, char_vocab_size, word_vocab_size):
        super().__init__()
        self.hidden = None # hidden state

        # architecture
        self.embed = embed(char_vocab_size, word_vocab_size, HRE)
        self.rnn = getattr(nn, RNN_TYPE)(
            input_size = EMBED_SIZE,
            hidden_size = HIDDEN_SIZE // NUM_DIRS,
            num_layers = NUM_LAYERS,
            bias = True,
            batch_first = True,
            dropout = DROPOUT,
            bidirectional = (NUM_DIRS == 2)
        )

    def init_state(self, b): # initialize RNN states
        n = NUM_LAYERS * NUM_DIRS
        h = HIDDEN_SIZE // NUM_DIRS
        hs = zeros(n, b, h) # hidden state
        if RNN_TYPE == "LSTM":
            cs = zeros(n, b, h) # LSTM cell state
            return (hs, cs)
        return hs

    def forward(self, b, xc, xw, mask):
        self.hidden = self.init_state(b)
        x = self.embed(xc, xw)
        x = nn.utils.rnn.pack_padded_sequence(x, mask[1], batch_first = True)
        h, _ = self.rnn(x, self.hidden)
        h, _ = nn.utils.rnn.pad_packed_sequence(h, batch_first = True)
        # TODO
        return h

class decoder(nn.Module):
    def __init__(self, char_vocab_size, word_vocab_size):
        super().__init__()
        self.hidden = None # hidden state

        # architecture
        self.embed = embed(char_vocab_size, word_vocab_size)
        self.rnn = getattr(nn, RNN_TYPE)(
            input_size = EMBED_SIZE,
            hidden_size = HIDDEN_SIZE // NUM_DIRS,
            num_layers = NUM_LAYERS,
            bias = True,
            batch_first = True,
            dropout = DROPOUT,
            bidirectional = (NUM_DIRS == 2)
        )
        self.attn = attn()
        self.softmax = nn.LogSoftmax(1)

    def forward(self, xc, xw, enc_out, t, mask):
        x = self.embed(xc, xw)
        h, _ = self.rnn(x, self.hidden)
        h = self.attn(h, enc_out, t, mask[0])
        y = self.softmax(h)
        return y

class attn(nn.Module): # content based input attention
    def __init__(self):
        super().__init__()
        self.a = None # attention weights (for heatmap)

        # architecture
        self.w1 = nn.Linear(HIDDEN_SIZE, HIDDEN_SIZE)
        self.w2 = nn.Linear(HIDDEN_SIZE, HIDDEN_SIZE)
        self.v = nn.Linear(HIDDEN_SIZE, 1)

    def forward(self, ht, hs, t, mask):
        a = self.v(torch.tanh(self.w1(hs) + self.w2(ht))) # [B, L, H] -> [B, L, 1]
        a = a.squeeze(2).masked_fill(mask, -10000) # masking in log space
        self.a = a
        return a # attention weights
