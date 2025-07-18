import codecs
import json
import logging
import os
import platform
import time
import zipfile
from datetime import datetime

import gspread
import wget
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import constants
from model.crawl_model import BijOfferItem, extract_integers_from_string
from model.sheet_model import BIJ
from utils.selenium_util import SeleniumUtil


## Retry functions

def get_cell_text(cell, retries=3):
    for _ in range(retries):
        try:
            return cell.text
        except StaleElementReferenceException:
            time.sleep(0.25)
    raise StaleElementReferenceException("Failed to get cell text after retries")


def get_row_elements(row, retries=3):
    while retries > 0:
        try:
            return row.find_elements(By.TAG_NAME, 'td')
        except StaleElementReferenceException:
            retries -= 1
            if retries == 0:
                raise
            time.sleep(0.25)


def find_link_element(cell, retries=3):
    for _ in range(retries):
        try:
            return cell.find_elements(By.TAG_NAME, 'a')[1]
        except StaleElementReferenceException:
            time.sleep(0.25)
    raise StaleElementReferenceException("Failed to find link element after retries")


def get_link_attribute(link_element, attribute='href', retries=3):
    for _ in range(retries):
        try:
            return link_element.get_attribute(attribute)
        except StaleElementReferenceException:
            time.sleep(0.25)
    raise StaleElementReferenceException(f"Failed to get attribute '{attribute}' after retries")


def get_row_elements_with_retries(row, retries=3):
    for _ in range(retries):
        try:
            return row.find_elements(By.TAG_NAME, 'td')
        except StaleElementReferenceException:
            time.sleep(0.25)
    raise StaleElementReferenceException("Failed to find row elements after retries")


def find_elements_with_retries(parent_element, by, value, retries=3):
    for _ in range(retries):
        try:
            return parent_element.find_elements(by, value)
        except StaleElementReferenceException:
            time.sleep(0.25)
    raise StaleElementReferenceException(f"Failed to find elements by {by}='{value}' after retries")


def get_hostname_by_host_id(data, hostid):
    for entry in data:
        if entry['hostid'] == str(hostid):
            return entry['hostname']
    return None


def bij_lowest_price(
        BIJ_HOST_DATA: dict,
        selenium: SeleniumUtil,
        data: BIJ,
        black_list) -> BijOfferItem:
    # print("herer")
    retries_time = constants.RETRIES_TIME
    data.BIJ_NAME = get_hostname_by_host_id(BIJ_HOST_DATA, data.BIJ_NAME)
    data.BIJ_NAME = str(data.BIJ_NAME) + " "
    selenium.get("https://www.bijiaqi.com/")
    try:
        wait = WebDriverWait(selenium.driver, constants.TIMEOUT)
        input_field = wait.until(EC.element_to_be_clickable((By.ID, 'speedhostname')))
        input_field.send_keys(data.BIJ_NAME)
        input_field.send_keys(Keys.BACKSPACE)
        input_field.send_keys(Keys.ENTER)
        time.sleep(1)
        table = None
        while retries_time > 0:
            try:
                table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'td table.tb.bijia.limit')))
                more_row = selenium.driver.find_element(By.XPATH, "//tr[@class='more']")
                selenium.driver.execute_script("arguments[0].click();", more_row)
                break
            except StaleElementReferenceException:
                retries_time -= 1
                if retries_time == 0:
                    raise
                time.sleep(0.25)

        data_array = []

        for row in find_elements_with_retries(table, By.TAG_NAME, 'tr', retries=retries_time):
            row_data = []
            for cell in get_row_elements_with_retries(row, retries=retries_time):
                cell_text = get_cell_text(cell, retries=retries_time)
                if cell_text == " ":
                    continue
                elif cell_text == "卖给他":
                    link_element = find_link_element(cell, retries=retries_time)
                    row_data.append(get_link_attribute(link_element, attribute='href', retries=retries_time))
                else:
                    row_data.append(cell_text)
            data_array.append(row_data)

        data_array = data_array[3:-2]
        results = list()
        for row in data_array:
            gold = extract_integers_from_string(row[2])
            if len(gold) == 2:
                min_gold = gold[0]
                max_gold = gold[1]
            else:
                min_gold = 0
                max_gold = 0
            result = BijOfferItem(
                username=str(row[0]),
                money=float(row[1]),
                gold=gold,
                min_gold=min_gold,
                max_gold=max_gold,
                dept=row[3],
                time=row[4],
                link=row[5],
                type=row[6],
                filter=row[7]
            )
            results.append(result)
        ans = list()
        for result in results:
            if result.type in data.BIJ_DELIVERY_METHOD and result.username not in black_list:
                if result.min_gold >= data.BIJ_STOCKMIN and result.max_gold <= data.BIJ_STOCKMAX:
                    ans = result
                    break
        return ans
    except Exception as e:
        raise RuntimeError(f"Error getting BIJ lowest price: {e}")
