import time

import torch
import torch_optimizer

import module

HIDDEN = 1024
DELAY = 8
BATCH_SIZE = 256
SEQUENCE_LENGTH = 256
DROPOUT_RATE = 0.15
PRINTERVALL = 64
DEVICE = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')


def init(module: torch.nn.Module):
    if hasattr(module, "weight") and hasattr(module.weight, "data"):
        if "norm" in module.__class__.__name__.lower() or (
                hasattr(module, "__str__") and "norm" in str(module).lower()):
            torch.nn.init.uniform_(module.weight.data, 0.998, 1.002)
        else:
            torch.nn.init.orthogonal_(module.weight.data)
    if hasattr(module, "bias") and hasattr(module.bias, "data"):
        torch.nn.init.constant_(module.bias.data, 0)


mod = torch.nn.Sequential(torch.nn.Embedding(256, 256),
                          module.RevRNN(256, HIDDEN, delay=DELAY, return_sequences=True),
                          module.Transpose(),
                          torch.nn.BatchNorm1d(HIDDEN),
                          torch.nn.Conv1d(HIDDEN, 256, 1)).to(DEVICE)
mod.apply(init)
opt = torch_optimizer.Yogi(mod.parameters(), lr=1e-3, weight_decay=1e-2)

tensor = torch.load('out.tensor')
tensor = tensor.long()

batch_index = torch.arange(0, BATCH_SIZE).view(1, -1)
item_index = torch.arange(0, SEQUENCE_LENGTH).view(-1, 1)
batch_index = batch_index + item_index
base_index = batch_index.clone()

length = tensor.size(0) // SEQUENCE_LENGTH - 1
len_len = len(str(length))

mean_loss = 0
curr_loss = 0
mean_acc = 0
torch.autograd.set_detect_anomaly(True)
while True:
    start_time = time.time()
    for i in range(1, 1 + length):
        tgt = tensor[batch_index].to(DEVICE)
        src = tgt * tgt.bernoulli(p=1-DROPOUT_RATE)
        out = mod(src.to(DEVICE))
        lss = torch.nn.functional.cross_entropy(out, tgt)
        lss.backward()
        opt.step()
        opt.zero_grad()
        curr_loss += lss.item()
        batch_index += SEQUENCE_LENGTH
        if i % PRINTERVALL == 0:
            mean_loss += curr_loss
            acc = (tgt == out.argmax(1)).sum().item() / tgt.numel() * 100
            mean_acc += acc
            print(f"[{i:{len_len}d}/{length}] Loss: {curr_loss / PRINTERVALL:7.4f} - Mean: {mean_loss / i:7.4f}"
                  f" | Acc: {acc:6.2f}% - Mean: {mean_acc / (i / PRINTERVALL):6.2f}%"
                  f" | Batch/s: {i / (time.time() - start_time):.3f}s")
            curr_loss = 0
