import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

# 1. Primera pàgina
url_llista = "https://valencianmusicoffice.com/va/artists?page=1"
res = requests.get(url_llista, headers=HEADERS)
soup = BeautifulSoup(res.text, "html.parser")

# 2. Primer artista
targeta = soup.select_one("div.site-wrapper a[href]")
url_artista = targeta["href"]

# 3. Fitxa de l’artista
res = requests.get(url_artista, headers=HEADERS)
soup = BeautifulSoup(res.text, "html.parser")

# 4. Printem tots els h3 per veure què conté exactament
print("🎯 TÍTOLS TROBATS:")
for h3 in soup.find_all("h3"):
    print("-", repr(h3.get_text(strip=True)))

# 5. Ara intentem buscar exactament el que volem
contacte_h3 = soup.find("h3", string="Contacte")
if contacte_h3:
    el = contacte_h3.find_next_sibling()
    while el and el.name == "p":
        print("📌", el.get_text(strip=True))
        el = el.find_next_sibling()
else:
    print("❌ No s'ha trobat cap <h3> exactament igual a 'Contacte'")
