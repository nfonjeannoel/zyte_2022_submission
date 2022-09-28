import copy
import json

import scrapy


class ZbotSpider(scrapy.Spider):
    name = 'zbot'
    # allowed_domains = ['x']
    start_urls = ['https://extract-summit-kokb7ng7-5umjfyjn4a-ew.a.run.app/']

    def parse(self, response):
        products = response.css("a[href*='click'] ::attr(href)").extract_first("")
        yield scrapy.Request(response.urljoin(products), callback=self.parse_products)

    def parse_products(self, response):
        products = response.css(".gtco-copy > a::attr(href)").extract()
        for product in products:
            yield scrapy.Request(response.urljoin(product), callback=self.parse_product)

        next_page = response.xpath("//a[text()[contains(., 'Next Page')]]").css("::attr(href)").extract_first()
        if next_page:
            yield scrapy.Request(url=response.urljoin(next_page), callback=self.parse_products)

    def parse_product(self, response):
        recommended_links = response.css(".team-item a")
        yield from response.follow_all(recommended_links, self.parse_product)

        item_id = response.css("#uuid::text").extract_first("").strip()
        name = response.css(".heading-colored::text").extract_first("").strip()
        image_id = response.css(".img-shadow img::attr(src)").re_first(r"gen/(.*)\.")
        if not image_id:
            script_xpath = "//script[contains(text(), 'mainimage')]"
            image_id_pattern = r"/([\da-f-]+)\.jpg"
            image_id = response.xpath(script_xpath).re_first(image_id_pattern)
        if not image_id:
            image_id = None

        rating = response.xpath("//p[text()[contains(., 'Rating')]] /span//text()").extract_first("").strip()
        p = r"from((.*));"
        phone_code = response.xpath("//script[text()[contains(., 'telephone ')]] //text()").re_first(p)
        if phone_code:
            phone_code = phone_code.strip()[2:-2]
            phone_code = "".join(chr(ord(i) - 16) for i in phone_code)

        data = response.css("#item-data-json::text").extract_first("")
        if data:
            data = json.loads(data)
            name = data.get("name", name)
            rating = data.get("rating", rating)
            image_new_id = data.get("image_path")
            if image_new_id:
                image_new_id = image_new_id.split("/")[-1].split(".")[0]
                image_id = image_new_id
            item_id = data.get("item_id", item_id)

        item = {
            "item_id": item_id,
            "name": name,
            "image_id": image_id,
            "rating": rating,
            "phone": phone_code.strip() or "",
        }

        if rating == 'NO RATING':
            rating_url = response.xpath("//p[text()[contains(., 'Rating')]] /span").css(
                "::attr(data-price-url)").extract_first("")
            meta = {"item": item}
            yield scrapy.Request(response.urljoin(rating_url), callback=self.parse_rating, meta=meta)

        else:
            yield item

    def parse_rating(self, response):
        item = copy.deepcopy(response.meta["item"])
        rating = json.loads(response.body.decode("utf-8"))
        item["rating"] = rating.get("value", "").strip()
        yield item
