import requests
from bs4 import BeautifulSoup
from lxml import html
import csv
import time
from urllib.parse import urljoin

BASE = "https://www.ptindirectory.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def safe_get(url):
    try:
        print("Fetching:", url)
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r
    except Exception as e:
        print("  Failed:", e)
        return None

def main():
    total_saved = 0
    total_skipped = 0

    # --------- GET STATES ---------
    home = safe_get(BASE)
    if not home:
        return

    home_soup = BeautifulSoup(home.text, "html.parser")

    states = []
    section = home_soup.find("h2", string=lambda x: x and "Tax Preparers by State" in x)
    if not section:
        print("Could not find 'Tax Preparers by State' section")
        return

    container = section.find_next("div")

    for a in container.find_all("a", href=True):
        state_name = a.get_text(strip=True)
        state_url = urljoin(BASE, a["href"])
        states.append((state_name, state_url))

    print("Found", len(states), "states")

    with open("tax_preparers.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["State", "City", "Name", "Address"])
        f.flush()

        # --------- LOOP STATES ---------
        for state_name, state_url in states:
            print(f"\nState: {state_name}")
            state_resp = safe_get(state_url)
            if not state_resp:
                print("Skipping state due to fetch failure:", state_url)
                continue

            state_soup = BeautifulSoup(state_resp.text, "html.parser")

            # City links
            city_links = []
            state_path = state_url.replace(BASE, "")

            for a in state_soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith(state_path) and href.count("/") == 3:
                    city_name = a.get_text(" ", strip=True)
                    city_name = city_name.rsplit("(", 1)[0].strip()

                    # Fallback: derive from URL if empty
                    if not city_name:
                        parts = href.strip("/").split("/")
                        if len(parts) >= 3:
                            city_name = parts[-1].replace("-", " ").title()

                    city_url = urljoin(BASE, href)
                    city_links.append((city_name, city_url))

            print("  Cities:", len(city_links))

            # --------- LOOP CITIES ---------
            for city_name, city_url in city_links:
                print(f"  City: {city_name}")
                city_resp = safe_get(city_url)
                if not city_resp:
                    print("Skipping city due to fetch failure:", city_url)
                    continue

                city_soup = BeautifulSoup(city_resp.text, "html.parser")

                # Collect only real profile links
                person_links = set()
                city_path = city_url.replace(BASE, "")

                for a in city_soup.find_all("a", href=True):
                    href = a["href"]
                    parts = href.strip("/").split("/")
                    # /tax-preparers/state/city/ID/slug
                    if href.startswith(city_path) and len(parts) >= 5 and parts[-2].isdigit():
                        person_links.add(urljoin(BASE, href))

                print("    Persons:", len(person_links))

                # --------- LOOP PERSONS ---------
                for person_url in person_links:
                    p_resp = safe_get(person_url)
                    if not p_resp:
                        print("Skipping person (fetch failed):", person_url)
                        total_skipped += 1
                        continue

                    tree = html.fromstring(p_resp.text)

                    # Name (robust + fallback)
                    name_list = tree.xpath('//*[@id="ae-skip-to-content"]//h4//text()')
                    name = " ".join(t.strip() for t in name_list if t.strip())

                    if not name:
                        title = tree.xpath('//title/text()')
                        if title:
                            name = title[0].split("|")[0].strip()

                    # Address
                    addr_list = tree.xpath('//span[@itemprop="address"]//text()')
                    address = " ".join(t.strip() for t in addr_list if t.strip()) if addr_list else ""

                    # DEBUG + SKIP (do not stop program)
                    if not state_name or not city_name or not name or not address:
                        print("\nSKIPPED RECORD")
                        print("State  :", repr(state_name))
                        print("City   :", repr(city_name))
                        print("Name   :", repr(name))
                        print("Address:", repr(address))
                        print("URL    :", person_url)
                        print("----------------------------")
                        total_skipped += 1
                        continue

                    if name.lower() == "ptindirectory":
                        print("Skipped placeholder page:", person_url)
                        total_skipped += 1
                        continue

                    total_saved += 1
                    writer.writerow([state_name, city_name, name, address])
                    f.flush()
                    print(f"      [{total_saved}] Saved: {name}")

                    time.sleep(0.2)

    print(f"\nDone!")
    print(f"Total records saved : {total_saved}")
    print(f"Total records skipped: {total_skipped}")
    print("All data saved to tax_preparers.csv")

if __name__ == "__main__":
    main()
