from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from bs4 import BeautifulSoup
import locale
from quixstreams import Application
import json
import logging

class Result:
    def __init__(self, name, amount, cost_unit):
        self.name = name
        self.amount = amount
        self.cost_unit = cost_unit

    def __str__(self):
        return f'name: {self.name}, amount: {self.amount}, const_unit: {self.cost_unit}'

    def to_dict(self):
        return {
            "name": self.name,
            "amount": self.amount,
            "cost_unit": self.cost_unit
        }


def parse(url: str) -> list[Result]:
    browser = webdriver.Chrome()
    browser.get(url)
    elem_click = browser.find_element(By.CLASS_NAME, 'collapsed')
    browser.execute_script("document.getElementsByClassName('collapsed')[0].click()")
    time.sleep(1)

    html = browser.page_source
    browser.quit()

    soup = BeautifulSoup(html, 'html.parser')
    elems_names = soup.find_all(name="strong", attrs={"data-bind": "text: Name"})
    elems_amounts = soup.find_all(name="td", attrs={"data-bind": "decimalAsText: Quantity"}, limit=len(elems_names))
    elems_costs_unit = soup.find_all(name="td", attrs={"data-bind": "decimalAsText: UnitPrice"}, limit=len(elems_names))

    names = [item.get_text() for item in elems_names]
    amounts = [item.get_text() for item in elems_amounts]
    costs_unit = [item.get_text() for item in elems_costs_unit]

    res = []
    locale.setlocale(locale.LC_NUMERIC, 'en_DK.UTF-8')
    for i in range(len(names)):
        res.append(Result(names[i], locale.atof(amounts[i]), locale.atof(costs_unit[i])))
    return res


def main():
    app = Application(
        broker_address='localhost:9092',
        loglevel='DEBUG',
        consumer_group='links_reader',
    )
    consumer = app.get_consumer()
    producer = app.get_producer()
    consumer.subscribe(['links'])
    while True:
        msg = consumer.poll(1)
        if msg is None:
            continue
        elif msg.error() is not None:
            raise Exception(msg.error())
        else:
            key = msg.key()
            if key is not None:
                key = key.decode('utf8')
            value = json.loads(msg.value())
            offset = msg.offset()

            transactions = parse(value)
            json_transactions = json.dumps([transaction.to_dict() for transaction in transactions]).encode('utf-8')

            logging.debug('Got transactions: %s', json_transactions)
            producer.produce(
                topic='transactions',
                value=json_transactions,
                partition=0,
                key=key
            )
            logging.info('Trnsactions produced')


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')
    main()
