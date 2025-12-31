if __name__ == "__main__":
    # Vytvoríme prázdny súbor na začiatku
    pd.DataFrame(columns=['SKU', 'Nazov', 'Pocet_ks', 'URL']).to_csv(VYSTUPNY_SUBOR, index=False, sep=';')
    
    # Najprv skúsime lokálny súbor (lebo vieme, že web nás blokuje)
    urls = []
    if os.path.exists('sitemap_basys.xml'):
        print("Našiel som lokálnu sitemapu (sitemap_basys.xml). Používam ju...")
        with open('sitemap_basys.xml', 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'lxml-xml')
            urls = [loc.text for loc in soup.find_all('loc') if loc.text and loc.text.endswith('.html')]
    
    # Ak lokálny súbor nie je, skúsime to predsa len z webu (ako zálohu)
    if not urls:
        urls = get_all_product_urls()

    if not urls:
        print("KONIEC: Nemám žiadne URL adresy. (Nahraj sitemap_basys.xml do repozitára!)")
        exit(0)

    print(f"Začínam spracovávať {len(urls)} produktov...")
    
    vysledky = []
    with requests.Session() as session:
        session.headers.update(HEADERS)
        # Tu znížime workerov na 3, aby nás neblokli pri sťahovaní samotných stránok
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(scrape_product_data, url, session) for url in urls]
            for i, future in enumerate(futures):
                res = future.result()
                if res:
                    vysledky.append(res)
                if (i + 1) % 50 == 0:
                    print(f"Spracované: {i + 1}/{len(urls)}")

    if vysledky:
        df = pd.DataFrame(vysledky)
        df.to_csv(VYSTUPNY_SUBOR, index=False, encoding='utf-8-sig', sep=';')
        print(f"HOTOVO! Súbor vytvorený s {len(vysledky)} položkami.")
