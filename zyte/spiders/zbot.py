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
        if not response.meta.get("seen"):
            sorting = response.css("a[href*='sort_by=alphabetically']::attr(href)").extract_first("")
            yield scrapy.Request(response.urljoin(sorting), callback=self.parse_products, meta={"seen": True})
        products = response.css(".gtco-practice-area-item .gtco-copy a::attr(href)").extract()
        # links = response.css("a::attr(href)").extract()
        # if len(links) != 22:
        #     yield {"url": response.url, "links": links}
        # self.log("url {} has {} products".format(response.url, len(links)))
        for product in products:
            yield scrapy.Request(response.urljoin(product), callback=self.parse_product)

        next_page = response.xpath("//a[text()[contains(., 'Next Page')]]").css("::attr(href)").extract()
        if next_page:
            for page in next_page:
                yield scrapy.Request(url=response.urljoin(page), callback=self.parse_products)

    def parse_product(self, response):
        recommended_links = response.css(".team-item a::attr(href)").extract()
        for link in recommended_links:
            yield scrapy.Request(response.urljoin(link), callback=self.parse_product)

        item_id = response.css("#uuid::text").extract_first("").strip()
        name = response.css(".heading-colored::text").extract_first("").strip()
        image_id_css = ".img-shadow ::attr(src)"
        image_id_pattern = r"/([\da-f-]+)\.jpg"
        image_id = response.css(image_id_css).re_first(image_id_pattern)
        if not image_id:
            script_xpath = "//script[contains(text(), 'mainimage')]"
            image_id = response.xpath(script_xpath).re_first(image_id_pattern)
        if not image_id:
            image_id = None

        rating = response.xpath("//p[text()[contains(., 'Rating')]] /span//text()").extract_first("").strip()
        p = r"from((.*));"
        phone_code = response.xpath("//script[text()[contains(., 'telephone ')]] //text()").re_first(p)
        if phone_code:
            phone_code = phone_code.strip()[2:-2]
            phone_code = "".join(chr(ord(i) - 16) for i in phone_code)
        else:
            phone_code = response.css('p:contains("Telephone") span ::text').extract_first()

        d = None
        if response.css('#uuid ::text').get() is None:
            d = json.loads(response.css('#item-data-json::text').extract_first())

            item_id = d['item_id']
            name = d['name']

            if image_id is None:
                if 'image_path' in d:
                    image_id = d['image_path']
                    image_id = image_id.split('/')[-1].split('.')[0]

        item = {
            "item_id": item_id,
            "name": name,
            "image_id": image_id,
            "rating": rating,
            "phone": phone_code.strip() or "",
        }

        rating = response.css('#item-data p:contains("Rating") span ::attr("data-price-url")').extract_first()
        if rating is not None:
            if rating[0] == '/':
                rating = response.urljoin(rating)
            yield scrapy.Request(url=rating,
                                 callback=self.parse_rating,
                                 errback=self.parse_rating_error,
                                 dont_filter=True,
                                 meta={'item': item})
        elif d is not None:
            if d.get('data_url') is not None:
                rating = response.urljoin(d['data_url'])
                yield scrapy.Request(url=rating,
                                     callback=self.parse_rating,
                                     errback=self.parse_rating_error,
                                     dont_filter=True,
                                     meta={'item': item})
            elif 'rating' in d:
                item['rating'] = d['rating']
                yield item
            else:
                yield item

        else:
            yield item

    def parse_rating(self, response):
        item = copy.deepcopy(response.meta["item"])
        rating = json.loads(response.body.decode("utf-8"))
        item["rating"] = rating.get("value", "").strip()

        yield item

    def parse_rating_error(self, response):
        item = response.meta.get('item')
        yield item
