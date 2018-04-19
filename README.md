# Encoder-Decoder RNNs in PyTorch

A PyTorch implementation of encoder-decoder RNNs for sequence to sequence learning, adapted from [the PyTorch tutorial](http://pytorch.org/tutorials/intermediate/seq2seq_translation_tutorial.html).

Supported features:
- Mini-batch training with CUDA
- Global attention (Luong 2015)

## Usage

Training data should be formatted as below:
```
source_sequence \t target_sequence
source_sequence \t target_sequence
...
```

To prepare data:
```
python prepare.py training_data
```

To train:
```
python train.py model vocab.src vocab.tgt training_data.csv num_epoch
```

To predict:
```
python predict.py model.epochN vocab.src vocab.tgt test_data
```

## References

Dzmitry Bahdanau, Kyunghyun Cho, Yoshua Bengio. 2015. Neural Machine Translation by Jointly Learning to Align and Translate. [arXiv:1409.0473 [cs.CL]](https://arxiv.org/abs/1409.0473).

Minh-Thang Luong, Hieu Pham, Christopher D. Manning. 2015. Effective Approaches to Attention-based Neural Machine Translation. [arXiv:1508.04025 [cs.CL]](https://arxiv.org/abs/1508.04025).
