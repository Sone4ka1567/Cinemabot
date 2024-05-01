import aiohttp
import tldextract

from urllib.parse import unquote
from bs4 import BeautifulSoup

from aiogram.utils.markdown import escape_md, link, text
from aiogram.utils.text_decorations import markdown_decoration as md


class WatchLinksAPI:
    def __init__(self) -> None:
        self.session = aiohttp.ClientSession()

    @staticmethod
    def add_watch_link(links: dict[str, str], site_url: str, url: str) -> dict[str, str]:
        extracted = tldextract.extract(site_url)
        domain_suff = extracted.domain + "." + extracted.suffix

        links[domain_suff] = url
        return links

    async def get_watch_movie_links(self, movie: dict[str, str | int], links_count: int = 5) -> dict[str, str]:
        links = dict()

        params = {"q": movie["name"] + " смотреть онлайн бесплатно"}
        headers = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:108.0) Gecko/20100101 Firefox/108.0"}

        async with self.session.get("https://www.google.com/search", params=params, headers=headers) as r:
            r.raise_for_status()
            response = await r.text()

            soup = BeautifulSoup(response, "html.parser")
            results = soup.find("div", attrs={"id": "rso"})
            hrefs = results.findChildren("a", recursive=True)

            for a_href in hrefs:
                if a_href is not None and "href" in a_href.attrs and not a_href.attrs["href"].startswith("/search"):
                    if "data-usg" not in a_href.attrs or "data-ved" not in a_href.attrs:
                        continue

                    site_url = unquote(a_href.attrs["href"])

                    if site_url.startswith("/"):
                        url_suff = site_url
                    else:
                        url_suff = "/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&ved={}&url={}&usg={}".format(
                            a_href.attrs["data-ved"],
                            site_url, a_href.attrs["data-usg"]
                        )

                    WatchLinksAPI.add_watch_link(links, site_url, "https://www.google.com" + url_suff)

                if len(links) >= links_count:
                    break

        return links

    @staticmethod
    def format_watch_links(movie: dict[str, str | int], links: dict[str, str]) -> str:
        txt = escape_md("По этим ссылкам ты можешь посмотреть \"") + \
            md.bold(escape_md(movie["name"])) + \
            escape_md(".\nОбрати внимание, некоторые из них ведут на платные ресурсы.")
        formatted_links = [txt, ""]

        for i, (domain, url) in enumerate(links.items()):
            formatted_links.append(link(domain, url))

        return text(*formatted_links, sep="\n")
