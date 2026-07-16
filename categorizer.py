"""
agentTrain.py – stabile Version (fixed)

Fixes:
- kein None in Embeddings mehr
- korrektes text_to_tensor (1 Rückgabewert, klar)
- Safe Handling für leere Embeddings
- robustes Training (kein vstack crash)
- keine Tuple-Verwechslungen
"""

import os
import re
import numpy as np
import torch
import torch.nn as nn
from torch.nn import functional as F
from sentence_transformers import SentenceTransformer
from sklearn.model_selection import train_test_split

# ── Config ─────────────────────────────────────────────
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

CATEGORIES = [
    "Important",
    "Newsletter",
    "Shopping",
    "Finance",
    "Notifications",
    "Spam",
]

INPUT_SIZE = 384
OUTPUT_SIZE = len(CATEGORIES)

MODEL_PATH = "multi_class_model.pth"
TRAIN_DATA_PATH = "QuotesNEw.txt"
EMBED_CACHE_PATH = "embed_cache.npz"

CONFIDENCE_THRESHOLD = 0.65
RETRAIN_THRESHOLD = 10
RETRAIN_EPOCHS = 30
RETRAIN_LR = 0.00005


# ── Model ─────────────────────────────────────────────
class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(INPUT_SIZE, 256)
        self.bn1 = nn.BatchNorm1d(256)
        self.fc2 = nn.Linear(256, 128)
        self.bn2 = nn.BatchNorm1d(128)
        self.fc3 = nn.Linear(128, 64)
        self.fc4 = nn.Linear(64, OUTPUT_SIZE)
        self.dropout = nn.Dropout(0.3)

    def forward(self, x):
        x = self.dropout(torch.relu(self.bn1(self.fc1(x))))
        x = self.dropout(torch.relu(self.bn2(self.fc2(x))))
        x = torch.relu(self.fc3(x))
        return F.log_softmax(self.fc4(x), dim=1)


# ── Embedder ─────────────────────────────────────────
print("[agentTrain] Lade Embedder...")
embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def text_to_vec(text: str):
    """Gibt IMMER einen validen embedding vector zurück."""
    if not text or not isinstance(text, str):
        text = "empty email"
    return embedder.encode(text)


# ── Globals ─────────────────────────────────────────
model = Net().to(DEVICE)

if os.path.exists(MODEL_PATH):
    model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    print("[agentTrain] Modell geladen.")
else:
    print("[agentTrain] Kein Modell gefunden → erst trainieren")

model.eval()

X_train = None
y_train = None
pending_examples = []


# ── Parser ─────────────────────────────────────────
def _parse_line(line):
    line = line.strip()
    if not line:
        return None

    if "\t" in line:
        parts = line.split("\t")
        if len(parts) < 2:
            return None
        text, label_str = parts[0], parts[-1]
    else:
        match = re.match(r"^(.*)\s+(\d+)$", line)
        if not match:
            return None
        text, label_str = match.group(1), match.group(2)

    if not label_str.isdigit():
        return None

    label = int(label_str)
    if label < 0 or label >= OUTPUT_SIZE:
        return None

    return text, label


def load_raw_dataset(path):
    texts, labels = [], []
    if not os.path.exists(path):
        return texts, labels

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parsed = _parse_line(line)
            if parsed:
                t, l = parsed
                texts.append(t)
                labels.append(l)

    return texts, labels


# ── Cache ─────────────────────────────────────────
def load_cache():
    if os.path.exists(EMBED_CACHE_PATH):
        data = np.load(EMBED_CACHE_PATH)
        return data["X"], data["y"]

    texts, labels = load_raw_dataset(TRAIN_DATA_PATH)
    if not texts:
        return None, None

    X = embedder.encode(texts, show_progress_bar=True)
    y = np.array(labels, dtype=np.int64)

    np.savez(EMBED_CACHE_PATH, X=X, y=y)
    return X, y


X_train, y_train = load_cache()


# ── Categorize ─────────────────────────────────────
def CategorizePost(content):
    vec = text_to_vec(content)

    tensor = torch.tensor(vec, dtype=torch.float32).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        probs = torch.exp(model(tensor))[0]
        pred = torch.argmax(probs).item()
        conf = probs[pred].item()

    return {
        "label": pred,
        "category": CATEGORIES[pred],
        "confidence": conf,
        "probabilities": probs.tolist(),
        "is_uncertain": conf < CONFIDENCE_THRESHOLD,
    }


# ── Learn correction ───────────────────────────────
def learn_correction(content, correct_label):
    if not (0 <= correct_label < OUTPUT_SIZE):
        raise ValueError("Invalid label")

    vec = text_to_vec(content)

    pending_examples.append((vec, correct_label))

    print(f"[learn] {CATEGORIES[correct_label]} ({len(pending_examples)}/{RETRAIN_THRESHOLD})")

    if len(pending_examples) >= RETRAIN_THRESHOLD:
        retrain()


# ── Retrain ────────────────────────────────────────
def retrain():
    global X_train, y_train, pending_examples

    if not pending_examples:
        return

    new_X = np.array([v for v, _ in pending_examples])
    new_y = np.array([l for _, l in pending_examples])

    if X_train is None:
        # First ever batch of corrections - these become the whole training set
        X_train = new_X
        y_train = new_y
    else:
        X_train = np.vstack([X_train, new_X])
        y_train = np.concatenate([y_train, new_y])

    idx = np.random.choice(len(X_train), min(1000, len(X_train)), replace=False)

    Xt = torch.tensor(X_train[idx], dtype=torch.float32).to(DEVICE)
    yt = torch.tensor(y_train[idx], dtype=torch.long).to(DEVICE)

    opt = torch.optim.Adam(model.parameters(), lr=RETRAIN_LR)
    loss_fn = nn.NLLLoss()

    model.train()
    for _ in range(RETRAIN_EPOCHS):
        opt.zero_grad()
        loss = loss_fn(model(Xt), yt)
        loss.backward()
        opt.step()

    model.eval()
    pending_examples = []

    torch.save(model.state_dict(), MODEL_PATH)
    np.savez(EMBED_CACHE_PATH, X=X_train, y=y_train)
    print("[retrain] done")


# ── Train from scratch ─────────────────────────────
def train_from_scratch():
    global model, X_train, y_train

    texts, labels = load_raw_dataset(TRAIN_DATA_PATH)

    X = embedder.encode(texts, show_progress_bar=True)
    y = np.array(labels)

    np.savez(EMBED_CACHE_PATH, X=X, y=y)

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y)

    model = Net().to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.NLLLoss()

    Xt = torch.tensor(Xtr, dtype=torch.float32).to(DEVICE)
    yt = torch.tensor(ytr).to(DEVICE)
    Xv = torch.tensor(Xte, dtype=torch.float32).to(DEVICE)
    yv = torch.tensor(yte).to(DEVICE)

    for i in range(100):
        model.train()
        opt.zero_grad()
        loss = loss_fn(model(Xt), yt)
        loss.backward()
        opt.step()

    torch.save(model.state_dict(), MODEL_PATH)
    model.eval()

    X_train, y_train = X, y


# ── Interactive ─────────────────────────────────────
def interactive_loop():
    print("start")

    while True:
        text = input("> ")
        if text in ["exit", "quit"]:
            break

        res = CategorizePost(text)

        print(res["category"], res["confidence"])

        user = input("label (empty = accept): ")

        if user == "":
            learn_correction(text, res["label"])
        elif user.isdigit():
            learn_correction(text, int(user))


if __name__ == "__main__":
    if not os.path.exists(MODEL_PATH):
        print("[agentTrain] Kein gespeichertes Modell - trainiere von Grund auf...")
        train_from_scratch()
    interactive_loop()