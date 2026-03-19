import numpy as np
import torch, torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error
from typing import List, Dict, Any
from loguru import logger

class MLP(nn.Module):
    def __init__(self, in_f, hidden, out_f=1, dropout=0.1):
        super().__init__()
        layers, prev = [], in_f
        for h in hidden:
            layers += [nn.Linear(prev,h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(dropout)]
            prev = h
        layers.append(nn.Linear(prev, out_f))
        self.net = nn.Sequential(*layers)
    def forward(self, x): return self.net(x)

def train_mlp(X, y, hidden_layers=None, epochs=200, lr=1e-3, batch_size=32):
    if hidden_layers is None: hidden_layers = [64, 32, 16]
    logger.info(f"MLP {hidden_layers} — {epochs} epochs")
    Xa, ya = np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)
    X_tr, X_te, y_tr, y_te = train_test_split(Xa, ya, test_size=0.2, random_state=42)
    sx, sy = StandardScaler(), StandardScaler()
    X_tr_s = sx.fit_transform(X_tr).astype(np.float32)
    X_te_s = sx.transform(X_te).astype(np.float32)
    y_tr_s = sy.fit_transform(y_tr.reshape(-1,1)).flatten().astype(np.float32)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ds = TensorDataset(torch.tensor(X_tr_s), torch.tensor(y_tr_s))
    loader = DataLoader(ds, batch_size=min(batch_size, len(ds)), shuffle=True)
    model = MLP(X_tr_s.shape[1], hidden_layers).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=20)
    crit = nn.MSELoss()
    X_te_t = torch.tensor(X_te_s).to(device)
    y_te_t = torch.tensor(sy.transform(y_te.reshape(-1,1)).flatten().astype(np.float32)).to(device)
    history = {"train_loss":[], "val_loss":[]}
    best_val, best_state = float("inf"), None
    for ep in range(epochs):
        model.train(); eloss = 0
        for xb,yb in loader:
            xb,yb = xb.to(device),yb.to(device)
            opt.zero_grad(); loss = crit(model(xb).squeeze(),yb); loss.backward(); opt.step()
            eloss += loss.item()
        tl = eloss/len(loader)
        model.eval()
        with torch.no_grad(): vl = crit(model(X_te_t).squeeze(),y_te_t).item()
        sched.step(vl)
        if vl < best_val: best_val=vl; best_state={k:v.clone() for k,v in model.state_dict().items()}
        if ep%20==0: history["train_loss"].append(round(tl,6)); history["val_loss"].append(round(vl,6))
    model.load_state_dict(best_state); model.eval()
    with torch.no_grad(): yps = model(X_te_t).squeeze().cpu().numpy()
    yp = sy.inverse_transform(yps.reshape(-1,1)).flatten()
    return {"model":"mlp","architecture":hidden_layers,"epochs":epochs,
            "test_r2":round(float(r2_score(y_te,yp)),6),
            "test_rmse":round(float(np.sqrt(mean_squared_error(y_te,yp))),6),
            "best_val_loss":round(best_val,6),"history":history,
            "predictions":yp.tolist(),"y_test":y_te.tolist(),"device":str(device)}

def train_hybrid_model(t_data, C_data, C0, k, epochs=300):
    logger.info("Entraînement modèle hybride Physique+NN")
    ta = np.array(t_data, dtype=np.float32)
    Ca = np.array(C_data, dtype=np.float32)
    C_phys = C0 * np.exp(-k * ta)
    sc = StandardScaler()
    Cs = sc.fit_transform(C_phys.reshape(-1,1)).astype(np.float32)
    Cas = sc.transform(Ca.reshape(-1,1)).flatten().astype(np.float32)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = nn.Sequential(nn.Linear(1,32),nn.Tanh(),nn.Linear(32,16),nn.Tanh(),nn.Linear(16,1)).to(device)
    opt = torch.optim.Adam(net.parameters(), lr=5e-4)
    crit = nn.MSELoss()
    Ct = torch.tensor(Cs).to(device); Cat = torch.tensor(Cas).to(device)
    history = []
    for ep in range(epochs):
        opt.zero_grad(); corr=net(Ct); loss=crit((Ct+corr).squeeze(),Cat); loss.backward(); opt.step()
        if ep%30==0: history.append(round(loss.item(),6))
    net.eval()
    with torch.no_grad(): corr_f = net(Ct).squeeze().cpu().numpy()
    Ch = sc.inverse_transform((Cs.flatten()+corr_f).reshape(-1,1)).flatten()
    return {"model":"hybrid_physics_nn","physics_r2":round(float(r2_score(Ca,C_phys)),6),
            "hybrid_r2":round(float(r2_score(Ca,Ch)),6),
            "improvement":round(float(r2_score(Ca,Ch)-r2_score(Ca,C_phys)),6),
            "t":ta.tolist(),"C_data":Ca.tolist(),"C_physics":C_phys.tolist(),"C_hybrid":Ch.tolist(),
            "training_history":history}
