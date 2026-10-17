# Client–Server Demo: Login Website

- **Client:** your web browser
- **Server:** `app.py`, a small Python web server on port 8080
- **Database:** `demo.db` (SQLite) with users, products and a login log

The site uses plain HTTP, so Wireshark can show every request, **including the password**.

## Start

Double-click **`start.bat`**. It starts the server and opens http://127.0.0.1:8080 in your browser.

Demo accounts: `admin / admin123`, `alice / password1`, `bob / qwerty`

## Wireshark

1. Open Wireshark and double-click **Adapter for loopback traffic capture**.
   If you use the site from another device (phone or second PC), pick **Ethernet / Wi-Fi** instead.
2. Filter: `tcp.port == 8080`

| Show | Filter |
|---|---|
| All demo traffic | `tcp.port == 8080` |
| Only HTTP requests | `http.request` |
| The login (password visible) | `http.request.method == "POST"` |
| Failed logins | `http.response.code == 401` |

To read the password: click the POST `/login` packet and expand **HTML Form URL Encoded**.
Or right-click the packet and choose **Follow → HTTP Stream**.

## Presentation flow

1. **Architecture.** The browser (client) sends requests, the server answers, and the server reads the database.
2. Start Wireshark with filter `tcp.port == 8080`, then open the site.
3. **Wrong password.** The server answers `401` and the attempt appears in the login log.
4. **Correct login.** In Wireshark, show the **TCP handshake** (SYN, SYN/ACK, ACK), then the
   `POST /login` with **the username and password in clear text**. The server replies
   `303` + `Set-Cookie: session=...`.
5. **Dashboard.** The browser sends the cookie with every request, which is how the server knows
   who you are. The product table comes from the database.
6. **Search** for "network". The query appears in the URL: `GET /dashboard?q=network`.
7. **Takeaway:** HTTP is readable by anyone on the network, which is why real sites use **HTTPS**.
   The database stores password *hashes*, not the passwords themselves.

To reset the data, stop the server and delete `demo.db`. The previous DNS version is in `old_version/`.
