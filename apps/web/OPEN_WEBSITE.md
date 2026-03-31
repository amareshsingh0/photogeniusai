# Website open nahi ho raha? Ye karo

## 0. Pehle ye test karo (React / Next bilkul nahi)
Browser mein **ye URL** kholo: **http://127.0.0.1:3004/ok.html**
(Port 3002, 3003, 3004 — jo bhi terminal mein "Ready:" ke baad likha ho.)
- **Agar "Server is working" dikhe** → server chal raha hai. Phir try karo: http://127.0.0.1:3004/
- **Agar blank / error / timeout** → URL galat hai ya firewall block kar raha hai. Check: same PC, 127.0.0.1, port terminal wala.

## 1. Dev server chalao
```powershell
cd "c:\desktop\PhotoGenius AI"
npx pnpm run dev
```

## 2. Terminal mein URL dekho
Jab sab start ho jaye, kuch aisa dikhega:
```
[run-web-dev] Ready: http://127.0.0.1:3002 — open this in your browser.
```
**Wahi URL copy karo** (3002, 3003, 3004... jo bhi likha ho).

## 3. Browser mein wahi URL kholo
- Chrome/Edge address bar mein paste karo
- **http://127.0.0.1:3002** (ya jo port terminal mein dikhe)
- **localhost** ki jagah **127.0.0.1** use karo (Windows pe better)

## 4. Agar phir bhi blank / loading
- **Ctrl+Shift+R** (hard refresh, cache clear)
- Naya **Incognito/Private** window khol ke wahi URL try karo
- **F12** → Console tab → koi **red error** hai? Screenshot bhejo

## 5. Port sahi hai?
Agar tum **3004** khol rahe ho lekin terminal mein **3002** likha hai, to 3002 kholo. Port hamesha terminal wala use karo.
