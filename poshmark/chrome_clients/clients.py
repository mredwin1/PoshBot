import datetime
import email
import imaplib
import os
import pickle
import random
import re
import requests
import socket
import string
import time
import traceback

from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from poshmark.models import PoshUser

CAPTCHA_API_KEY = os.environ['CAPTCHA_API_KEY']


class Logger:
    def __init__(self, logger_id, log_function):
        self.logger_id = logger_id
        self.log_function = log_function

    def critical(self, message):
        self.log_function(str(self.logger_id), {'level': 'CRITICAL', 'message': message})

    def error(self, message):
        self.log_function(str(self.logger_id), {'level': 'ERROR', 'message': message})

    def warning(self, message):
        self.log_function(str(self.logger_id), {'level': 'WARNING', 'message': message})

    def info(self, message):
        self.log_function(str(self.logger_id), {'level': 'INFO', 'message': message})

    def debug(self, message):
        self.log_function(str(self.logger_id), {'level': 'DEBUG', 'message': message})


class Captcha:
    def __init__(self, google_key, page_url, logger):
        self.request_id = None
        self.google_key = google_key
        self.page_url = page_url
        self.logger = logger

    def send_captcha(self):
        url = 'https://2captcha.com/in.php'
        params = {
            'key': CAPTCHA_API_KEY,
            'method': 'userrecaptcha',
            'googlekey': self.google_key,
            'pageurl': self.page_url,
            'json': '1'
        }
        response = requests.get(url, params=params).json()
        if response['status'] == 1:
            self.request_id = response['request']
            return True
        else:
            self.logger.error(f'reCaptcha request failed! Error code: {response["request"]}')
            return False

    def get_response(self):
        url = 'https://2captcha.com/res.php'
        params = {
            'key': CAPTCHA_API_KEY,
            'json': 1,
            'action': 'get',
            'id': self.request_id
        }
        response = requests.get(url, params=params).json()

        if response['status'] == 0:
            if 'ERROR' in response['request']:
                self.logger.error(f"[!] Captcha error: {response['request']}")
                if response['request'] == 'ERROR_CAPTCHA_UNSOLVABLE':
                    return -2
                return -1
            return None
        else:
            return response['request']

    def solve_captcha(self):
        self.send_captcha()
        time.sleep(20)

        while True:
            response = self.get_response()
            if response:
                if response == -1:
                    return -1
                elif response == -2:
                    return None
                else:
                    return response
            time.sleep(5)


class PhoneNumber:
    def __init__(self, service_name, logger, api_key):
        self.service_name = service_name
        self.logger = logger
        self.headers = {
            'X-API-KEY': api_key
        }
        self.order_id = None
        self.number = None
        self.reuse = False

    def _check_order_history(self, excluded_numbers=None):
        selected_service = 'Google / Gmail / Google Voice / Youtube' if self.service_name == 'google' else 'Poshmark'
        order_history_url = 'https://portal.easysmsverify.com/get_order_history'

        response = None

        while not response or response.status_code != requests.codes.ok:
            response = requests.get(order_history_url, headers=self.headers)

        response_json = response.json()

        organized_orders = {}
        for order in response_json['order_history']:
            if order['state'] == 'FINISHED':
                try:
                    service = organized_orders[order['service_name']]
                    try:
                        service[order['number']]['quantity'] += 1
                    except KeyError:
                        service[order['number']] = {
                            'quantity': 1,
                            'order_id': order['order_id']
                        }
                except KeyError:
                    organized_orders[order['service_name']] = {
                        order['number']: {
                            'quantity': 1,
                            'order_id': order['order_id']
                        }
                    }

        try:
            for key, value in organized_orders[selected_service].items():
                try:
                    if value['quantity'] < 3 and key not in excluded_numbers:
                        self.number = key
                        self.order_id = value['order_id']
                        self.reuse = True
                        return key
                except ValueError:
                    pass
        except KeyError:
            pass
        return None

    def get_number(self, excluded_numbers=None, state=None):
        number = self._check_order_history(excluded_numbers)
        if number:
            self.logger.info(f'Reusing number {number}')
            return number
        else:
            service_id_url = 'https://portal.easysmsverify.com/get_service_id'
            phone_number_url = 'https://portal.easysmsverify.com/order_number'

            service_id_parameters = {
                'service_name': self.service_name
            }
            service_id_response = None

            while not service_id_response or service_id_response.status_code != requests.codes.ok:
                service_id_response = requests.post(service_id_url, headers=self.headers, data=service_id_parameters)

            service_id_response_json = service_id_response.json()

            if service_id_response_json['status']:
                service_id = service_id_response_json['service']['id']
                phone_number_parameters = {
                    'service_id': service_id,
                }

                if state:
                    phone_number_parameters['state'] = state

                phone_number_response = None

                while not phone_number_response or phone_number_response.status_code != requests.codes.ok:
                    phone_number_response = requests.post(phone_number_url, headers=self.headers, data=phone_number_parameters)

                phone_number_response_json = phone_number_response.json()

                if phone_number_response_json['status']:
                    phone_number = phone_number_response_json['number']
                    order_id = phone_number_response_json['order_id']
                    self.order_id = order_id
                    self.number = phone_number

                    self.logger.info(f'Using a new number: {phone_number}')

                    return phone_number
                else:
                    error_msg = phone_number_response_json['msg']
                    self.logger.error(error_msg)
            else:
                error_msg = f'{service_id_response_json["error_code"]} - {service_id_response_json["msg"]}'
                self.logger.error(error_msg)

    def get_verification_code(self):
        if self.reuse:
            order_number_url = 'https://portal.easysmsverify.com/order_number'
            parameters = {
                'previous_order_id': self.order_id
            }
            order_response = None
            order_response_json = {'status': False}
            attempts = 0
            while (not order_response or order_response.status_code != requests.codes.ok) and not order_response_json['status'] and attempts < 4:
                order_response = requests.post(order_number_url, headers=self.headers, data=parameters)
                if order_response or order_response.status_code == requests.codes.ok:
                    order_response_json = order_response.json()
                    if not order_response_json['status']:
                        self.logger.warning(order_response_json['msg'])
                        self.logger.info('Sleeping for 30 seconds')
                        order_response = None
                        order_response_json = {'status': False}
                        time.sleep(30)
                        attempts += 1

            if attempts >= 4:
                self.logger.warning('Number seems to be very busy skipping')
                return None

            self.order_id = order_response_json['order_id']

        check_sms_url = 'https://portal.easysmsverify.com/check_sms'
        parameters = {
            'order_id': self.order_id,
            'number': self.number
        }
        verification_response = None
        verification_response_json = {'state': 'WAITING_FOR_SMS'}

        while (not verification_response or verification_response.status_code != requests.codes.ok) or verification_response_json['state'] == 'WAITING_FOR_SMS':
            verification_response = requests.post(check_sms_url, headers=self.headers, data=parameters)

            if verification_response or verification_response.status_code == requests.codes.ok:
                verification_response_json = verification_response.json()
                if verification_response_json['state'] == 'WAITING_FOR_SMS':
                    self.logger.info('SMS not received, sleeping for 10 seconds')
                    time.sleep(10)

        if verification_response_json['state'] == 'ERROR':
            self.logger.error(verification_response_json['msg'])
            return None
        elif verification_response_json['state'] == 'SMS_RECEIVED':
            self.logger.info(f'Verification code received: {verification_response_json["code"]}')
            return verification_response_json['code']
        elif verification_response_json['state'] == 'TIME_OUT':
            self.logger.warning('Verification code note received in the allotted time')
            return None
        elif verification_response_json['state'] == 'CANCELLED':
            self.logger.warning('Phone number cancelled by user')
            return None


class BaseClient:
    def __init__(self, logger_id, log_function, proxy_ip=None, proxy_port=None):
        proxy = Proxy()
        hostname = proxy_ip if proxy_ip and proxy_port else ''
        port = proxy_port if proxy_ip and proxy_port else ''
        proxy.proxy_type = ProxyType.MANUAL if proxy_ip and proxy_port else ProxyType.SYSTEM

        if proxy_ip:
            proxy.http_proxy = '{hostname}:{port}'.format(hostname=hostname, port=port)
            proxy.ssl_proxy = '{hostname}:{port}'.format(hostname=hostname, port=port)

        capabilities = webdriver.DesiredCapabilities.CHROME
        proxy.add_to_capabilities(capabilities)

        self.web_driver = None
        self.web_driver_options = Options()
        self.web_driver_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.web_driver_options.add_experimental_option('useAutomationExtension', False)
        self.web_driver_options.add_argument('--disable-extensions')
        self.web_driver_options.add_argument('--headless')
        self.web_driver_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                             '(KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36')
        self.web_driver_options.add_argument('--incognito')
        self.web_driver_options.add_argument('--no-sandbox')

        self.logger = Logger(logger_id, log_function)

    def __enter__(self):
        self.open()

        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def open(self):
        """Used to open the selenium web driver session"""
        self.web_driver = webdriver.Chrome('/poshmark/chrome_clients/chromedriver', options=self.web_driver_options)
        self.web_driver.implicitly_wait(20)
        if '--headless' in self.web_driver_options.arguments:
            self.web_driver.set_window_size(1920, 1080)

    def close(self):
        """Closes the selenium web driver session"""
        self.web_driver.quit()

    def locate(self, by, locator, location_type=None):
        """Locates the first elements with the given By"""
        wait = WebDriverWait(self.web_driver, 30)
        if location_type:
            if location_type == 'visibility':
                return wait.until(EC.visibility_of_element_located((by, locator)))
            elif location_type == 'clickable':
                return wait.until(EC.element_to_be_clickable((by, locator)))
            else:
                return None
        else:
            return wait.until(EC.presence_of_element_located((by, locator)))

    def locate_all(self, by, locator, location_type=None):
        """Locates all web elements with the given By and returns a list of them"""
        wait = WebDriverWait(self.web_driver, 30)
        if location_type:
            if location_type == 'visibility':
                return wait.until(EC.visibility_of_all_elements_located((by, locator)))
            else:
                return None
        else:
            return wait.until(EC.presence_of_all_elements_located((by, locator)))

    def is_present(self, by, locator):
        """Checks if a web element is present"""
        try:
            self.web_driver.find_element(by=by, value=locator)
        except NoSuchElementException:
            return False
        return True

    def sleep(self, lower, upper=None):
        """Will simply sleep and log the amount that is sleeping for, can also be randomized amount of time if given the
        upper value"""
        seconds = random.randint(lower, upper) if upper else lower
        word = 'second' if seconds == 1 else 'seconds'

        self.logger.info(f'Sleeping for {seconds} {word}')
        time.sleep(seconds)


class GmailClient(BaseClient):
    def __init__(self, user_info, logger_id, log_function):
        super(GmailClient, self).__init__(logger_id, log_function)

        self.user_info = user_info

    def is_logged_in(self):
        """Checks if the user is singed into gmail"""
        try:
            self.logger.info('Checking if someone is logged in')
            self.web_driver.get('https://gmail.com')

            profile_icon = self.is_present(By.XPATH, '/html/body/div[7]/div[3]/div/div[1]/div[3]/header/div[2]/div[3]/div[1]/div[2]/div/a/img')

            if profile_icon:
                self.logger.info('Someone was logged in')
                return True
            else:
                self.logger.info('No one was logged in')
                return False

        except Exception as e:
            self.logger.error(traceback.format_exc())

    def register(self):
        """Registers a new gmail"""
        try:
            self.logger.info(f'Registering {self.user_info["first_name"]} {self.user_info["last_name"]}')

            self.web_driver.get('https://gmail.com')
            create_account_button = self.locate(
                By.XPATH,
                '//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[2]/div/div/div[1]/div/button/span'
            )
            create_account_button.click()

            for_my_self_button = self.locate(
                By.XPATH,
                '//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[2]/div/div/div[2]/div/ul/li[1]'
            )
            for_my_self_button.click()

            first_name_field = self.locate(By.ID, 'firstName')
            last_name_field = self.locate(By.ID, 'lastName')
            username_field = self.locate(By.ID, 'username')
            password_field = self.locate(By.XPATH, '//*[@id="passwd"]/div[1]/div/div[1]/input')
            confirm_field = self.locate(By.XPATH, '//*[@id="confirm-passwd"]/div[1]/div/div[1]/input')
            next_button = self.locate(By.XPATH, '//*[@id="accountDetailsNext"]/div/button')

            first_name_field.send_keys(self.user_info['first_name'])
            last_name_field.send_keys(self.user_info['last_name'])
            username_field.send_keys(self.user_info['email'])
            password_field.send_keys(self.user_info['password'])
            confirm_field.send_keys(self.user_info['password'])

            username = self.user_info['email']
            while self.is_present(By.XPATH, '//*[@id="view_container"]/div/div/div[2]/div/div[1]/div/form/span/section/div/div/div[2]/div[1]/div/div[2]/div[2]/div'):
                if self.is_present(By.XPATH, '//*[@id="view_container"]/div/div/div[2]/div/div[1]/div/form/span/section/div/div/div[2]/div[2]/div/ul/li[2]/button'):
                    other_email = self.locate(By.XPATH, '//*[@id="view_container"]/div/div/div[2]/div/div[1]/div/form/span/section/div/div/div[2]/div[2]/div/ul/li[2]/button')
                    username = other_email.text
                    other_email.click()
                else:
                    username_field = self.locate(By.ID, 'username')
                    username += str(random.randint(100, 999))
                    username.clear()
                    username_field.send_keys(username)
                    username_field.send_keys(Keys.TAB)

            self.user_info['email'] = f'{username}@gmail.com'

            next_button.click()

            if self.is_present(By.ID, 'phoneNumberId'):
                verification_code = None
                excluded_numbers = []
                while not verification_code:
                    phone_number = PhoneNumber('google', self.logger, os.environ['SMS_API_KEY'])
                    while not phone_number.number:
                        selected_number = str(phone_number.get_number(excluded_numbers=excluded_numbers))
                        phone_number_field = self.locate(By.ID, 'phoneNumberId')
                        phone_number_field.clear()
                        phone_number_field.send_keys(selected_number)

                        next_button = self.locate(
                            By.XPATH,
                            '//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[1]/div/div/button'
                        )
                        next_button.click()

                        if self.is_present(By.XPATH, '//*[@id="view_container"]/div/div/div[2]/div/div[1]/div/form/span/section/div/div/div[2]/div/div[2]/div[2]/div[2]/div'):
                            phone_number.number = None
                            phone_number.reuse = False
                            excluded_numbers.append(selected_number)

                    code_input = self.locate(By.ID, 'code')
                    verify_button = self.locate(By.XPATH, '//*[@id="view_container"]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div/button')

                    verification_code = phone_number.get_verification_code()

                    if not verification_code:
                        self.logger.warning('Trying again since there is no verification code.')
                        excluded_numbers.append(phone_number.number)
                        phone_number.number = None
                        phone_number.reuse = False
                        back_button = self.locate(By.XPATH, '//*[@id="view_container"]/div/div/div[2]/div/div[2]/div[1]/div/div/button')
                        back_button.click()
                    else:
                        code_input.send_keys(verification_code)
                        verify_button.click()

            time.sleep(2)

            gender_select = Select(self.locate(By.ID, 'gender'))
            month_select = Select(self.locate(By.ID, 'month'))
            day_field = self.locate(By.ID, 'day')
            year_field = self.locate(By.ID, 'year')

            day_field.send_keys(self.user_info['dob_day'])
            year_field.send_keys(self.user_info['dob_year'])
            month_select.select_by_visible_text(self.user_info['dob_month'])
            gender_select.select_by_visible_text(self.user_info['gender'])

            next_button = self.locate(
                By.XPATH,
                '//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[1]/div/div/button'
            )
            next_button.click()

            self.sleep(3)

            skip_button = self.locate(By.XPATH, '//*[@id="view_container"]/div/div/div[2]/div/div[2]/div[2]/div[2]/div/div/button')
            skip_button.click()

            self.sleep(3)

            body = self.locate(By.CSS_SELECTOR, 'body')
            body.send_keys(Keys.PAGE_DOWN)
            body.send_keys(Keys.PAGE_DOWN)

            agree_button = self.locate(By.XPATH, '//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[1]/div')
            agree_button.click()

            attempts = 0
            logo = self.is_present(By.XPATH, '//*[@id="gb"]/div[2]/div[1]/div[4]/div/a/img')
            while not logo and attempts <= 10:
                self.logger.error('Email not ready yet')
                self.sleep(5)
                logo = self.is_present(By.XPATH, '//*[@id="gb"]/div[2]/div[1]/div[4]/div/a/img')
                attempts += 1

                if self.is_present(By.XPATH, '//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[1]/div'):
                    agree_button = self.locate(By.XPATH, '//*[@id="view_container"]/div/div/div[2]/div/div[2]/div/div[1]/div', 'clickable')
                    agree_button.click()

            else:
                if attempts > 10:
                    self.logger.error(f'Email seems to have never been made')
                    return False
                else:
                    self.logger.info('Email creation success')
            import logging
            logging.info(self.user_info['email'])
            return self.user_info['email']
        except Exception as e:
            self.logger.error(str(traceback.format_exc()))

    def login(self):
        """Log user into gmail"""
        try:
            self.logger.info('Logging In')
            self.web_driver.get('https://www.google.com/gmail/')

            sign_in_button = self.locate(By.XPATH, '/html/body/div/header/div/div/ul/li[2]/a')
            sign_in_button.click()

            if self.is_present(By.XPATH, '/html/body/div[1]/div[1]/div[2]/div/div[2]/div/div/div[2]/div/div[1]/div/form/span/section/div/div/div/div/ul/li[2]/div/div'):
                self.logger.info('Other account button found, clicking it.')
                other_account_button = self.locate(By.XPATH, '/html/body/div[1]/div[1]/div[2]/div/div[2]/div/div/div[2]/div/div[1]/div/form/span/section/div/div/div/div/ul/li[2]/div/div')
                other_account_button.click()

            self.sleep(3)

            email_field = self.locate(By.XPATH, '/html/body/div[1]/div[1]/div[2]/div/div[2]/div/div/div[2]/div/div[1]/div/form/span/section/div/div/div[1]/div/div[1]/div/div[1]/input')
            next_button = self.locate(By.XPATH, '//*[@id="identifierNext"]/div/button')

            email_field.send_keys(self.user_info['email'])
            next_button.click()

            password_field = self.locate(By.XPATH, '/html/body/div[1]/div[1]/div[2]/div/div[2]/div/div/div[2]/div/div[1]/div/form/span/section/div/div/div[1]/div[1]/div/div/div/div/div[1]/div/div[1]/input')
            next_button = self.locate(By.XPATH, '//*[@id="passwordNext"]/div/button')

            password_field.send_keys(self.user_info['password'])
            next_button.click()

            not_now = self.is_present(By.XPATH, '//*[@id="yDmH0d"]/c-wiz/div/div/div/div[2]/div[4]/div[1]/span')
            if not_now:
                not_now_button = self.locate(By.XPATH, '//*[@id="yDmH0d"]/c-wiz/div/div/div/div[2]/div[4]/div[1]/span')
                not_now_button.click()

            self.logger.info('Successfully logged in')

            return True

        except Exception as e:
            self.logger.error(traceback.format_exc())
            return False

    def log_out(self):
        """Logs out of gmail"""
        try:
            self.logger.info('Logging out')

            self.web_driver.get('https://gmail.com')

            profile_icon = self.locate(By.XPATH, '/html/body/div[7]/div[3]/div/div[1]/div[3]/header/div[2]/div[3]/div[1]/div[2]/div/a/img')
            profile_icon.click()

            self.sleep(1)

            sign_out_button = self.locate(By.XPATH, '/html/body/div[7]/div[3]/div/div[1]/div[3]/header/div[2]/div[4]/div[4]/a')
            sign_out_button.click()

        except Exception as e:
            self.logger.error(traceback.format_exc())

    def allow_less_secure_apps(self):
        """Goes to the signed in gmail account and enables less secure apps"""
        try:
            self.web_driver.get('https://myaccount.google.com/security')

            self.sleep(2)

            body = self.locate(By.CSS_SELECTOR, 'body')
            body.send_keys(Keys.PAGE_DOWN)
            body.send_keys(Keys.PAGE_DOWN)

            self.sleep(1)

            off_button = self.locate(By.XPATH, '//*[@id="yDmH0d"]/c-wiz/div/div[2]/c-wiz/c-wiz/div/div[3]/div/div/c-wiz/section/div[6]/div/div/div[2]/div/a')
            off_button.click()

            allow_button = self.locate(By.ID, 'i3')
            allow_button.click()

            return True
        except Exception as e:
            self.logger.error(traceback.format_exc())
            return False

    def turn_on_email_forwarding(self, forwarding_address, password):
        """Enable email forwarding"""
        try:
            if self.is_logged_in():
                self.log_out()

            self.login()

            self.web_driver.get('https://gmail.com')

            if self.is_present(By.XPATH, '/html/body/div[22]'):
                overlay = self.locate(By.XPATH, '/html/body/div[22]')
                overlay.click()

            settings_button = self.locate(By.XPATH, '//*[@id="gb"]/div[2]/div[2]/div[3]/div[3]/a')
            settings_button.click()

            self.sleep(1)

            all_settings_button = self.locate(By.XPATH, '/html/body/div[7]/div[3]/div/div[2]/div[1]/div[3]/div[1]/div[1]/div[1]/div/button[2]')
            all_settings_button.click()

            forwarding_button = self.locate(By.XPATH, '/html/body/div[7]/div[3]/div/div[2]/div[1]/div[2]/div/div/div/div/div[1]/div/div[2]/div[6]/a')
            forwarding_button.click()

            window_before = self.web_driver.window_handles[0]

            add_address_button = self.locate(By.XPATH, '/html/body/div[7]/div[3]/div/div[2]/div[1]/div[2]/div/div/div/div/div[2]/div/div[1]/div/div/div/div/div/div/div[6]/div/table/tbody/tr[1]/td[2]/div/div[2]/input')
            add_address_button.click()

            email_pop_up = self.locate(By.CLASS_NAME, 'Kj-JD')
            email_field = email_pop_up.find_element_by_tag_name('input')
            next_button = email_pop_up.find_element_by_tag_name('button')

            email_field.send_keys(forwarding_address)
            next_button.click()

            window_after = self.web_driver.window_handles[1]

            self.web_driver.switch_to_window(window_after)

            accept_button = self.locate(By.XPATH, '/html/body/form/table/tbody/tr/td/input[3]')
            accept_button.click()

            self.web_driver.switch_to_window(window_before)

            confirmation_pop_up = self.locate(By.CLASS_NAME, 'Kj-JD')
            ok_button = confirmation_pop_up.find_element_by_tag_name('button')

            ok_button.click()

            self.logger.info('Getting verification code')

            verification_code_attempts = 0
            verification_code = None
            while not verification_code and verification_code_attempts < 6:
                verification_code = self.get_verification_code(forwarding_address, password)
                if not verification_code:
                    self.logger.error('Verification code not available, trying again')
                    self.sleep(60)

            if verification_code:
                verification_code_field = self.locate(By.XPATH, '/html/body/div[7]/div[3]/div/div[2]/div[1]/div[2]/div/div/div/div/div[2]/div/div[1]/div/div/div/div/div/div/div[6]/div/table/tbody/tr[1]/td[2]/div/div[3]/table/tbody/tr[4]/td[2]/input[1]')
                verify_button = self.locate(By.XPATH, '/html/body/div[7]/div[3]/div/div[2]/div[1]/div[2]/div/div/div/div/div[2]/div/div[1]/div/div/div/div/div/div/div[6]/div/table/tbody/tr[1]/td[2]/div/div[3]/table/tbody/tr[4]/td[2]/input[2]')

                verification_code_field.clear()

                verification_code_field.send_keys(verification_code)
                verify_button.click()

                enable_button = self.locate(By.XPATH, '/html/body/div[7]/div[3]/div/div[2]/div[1]/div[2]/div/div/div/div/div[2]/div/div[1]/div/div/div/div/div/div/div[6]/div/table/tbody/tr[1]/td[2]/div/div[1]/table[2]/tbody/tr/td[1]/input')
                enable_button.click()

            imap_enable_button = self.locate(By.XPATH, '/html/body/div[7]/div[3]/div/div[2]/div[1]/div[2]/div/div/div/div/div[2]/div/div[1]/div/div/div/div/div/div/div[6]/div/table/tbody/tr[3]/td[2]/div[1]/table[1]/tbody/tr/td[1]/input')
            imap_enable_button.click()

            return True

        except Exception as e:
            self.logger.error(traceback.format_exc())
            return False

    def get_verification_code(self, forwarding_address, password):
        """Gets the email forwarding verification code using imap"""
        try:
            attempts = 0
            socket.setdefaulttimeout(5)
            imap = imaplib.IMAP4_SSL('imap.gmail.com')
            imap.login(forwarding_address, password)

            imap.select('inbox')
            data = imap.search(None, f'(SUBJECT "Receive Mail from {self.user_info["email"]}")')  # (SUBJECT "Receive Mail from")

            mail_ids = data[1]
            id_list = mail_ids[0].split(b' ')
            id_list = [email_id.decode('utf-8') for email_id in id_list]
            id_list.reverse()

            for email_id in id_list:
                data = imap.fetch(email_id, '(RFC822)')
                for response_part in data:
                    arr = response_part[0]
                    if isinstance(arr, tuple):
                        msg = email.message_from_string(str(arr[1], 'utf-8'))
                        email_subject = msg['subject']
                        self.logger.debug(f'Email: {self.user_info["email"]} Subject: {email_subject}')
                        if self.user_info['email'] in email_subject:
                            hash_index = email_subject.find('#')
                            parenthesis_index = email_subject.find(')')
                            verification_code = email_subject[hash_index + 1:parenthesis_index]

                            self.logger.info(f'Verification code retrieved successfully: {verification_code}')

                            return verification_code
                self.logger.warning('Verification code not ready')
                time.sleep(60)
                attempts += 1

            self.logger.error('Could not get verification code from email')
            return None
        except Exception as e:
            self.logger.error(traceback.format_exc())
            return None

class PoshMarkClient(BaseClient):
    def __init__(self, redis_posh_user_id, redis_campaign_id, logger_id, log_function, get_redis_object_attr,
                 update_redis_object, redis_proxy_id=None):
        hostname = get_redis_object_attr(redis_proxy_id, 'ip') if redis_proxy_id else ''
        port = get_redis_object_attr(redis_proxy_id, 'port') if redis_proxy_id else ''
        super(PoshMarkClient, self).__init__(logger_id, log_function, hostname, port)

        self.redis_posh_user_id = redis_posh_user_id
        self.redis_campaign_id = redis_campaign_id
        self.get_redis_object_attr = get_redis_object_attr
        self.update_redis_object = update_redis_object
        self.requests_proxy = {
            'https': f'http://{hostname}:{port}',
        }
        self.last_login = None
        self.login_error = None

    def check_for_errors(self):
        """This will check for errors on the current page and handle them as necessary"""
        self.logger.info('Checking for errors')
        captcha_errors = [
            'Invalid captcha',
            'Please enter your login information and complete the captcha to continue.'
        ]
        error_classes = ['form__error-message', 'base_error_message', 'error_banner']
        present_error_classes = []

        for error_class in error_classes:
            if self.is_present(By.CLASS_NAME, error_class):
                present_error_classes.append(error_class)

        if not present_error_classes:
            self.logger.info('No known errors encountered')

        for present_error_class in present_error_classes:
            if 'form__error' in present_error_class:
                errors = self.locate_all(By.CLASS_NAME, present_error_class)
                error_texts = [error.text for error in errors]
                self.logger.error(f"The following form errors were found: {','.join(error_texts)}")

                return 'ERROR_FORM_ERROR'
            else:
                error = self.locate(By.CLASS_NAME, present_error_class)
                if error.text == 'Invalid Username or Password':
                    self.logger.error(f'Invalid Username or Password')
                    self.update_redis_object(self.redis_posh_user_id, {'status': PoshUser.INACTIVE})

                    return 'ERROR_USERNAME_PASSWORD'

                elif error.text in captcha_errors:
                    self.logger.warning('Captcha encountered')
                    captcha_iframe = self.locate(By.TAG_NAME, 'iframe', location_type='visibility')
                    captcha_src = captcha_iframe.get_attribute('src')
                    google_key = re.findall(r'(?<=k=)(.*?)(?=&)', captcha_src)[0]

                    captcha_solver = Captcha(google_key, self.web_driver.current_url, self.logger)
                    captcha_response = captcha_solver.solve_captcha()
                    retries = 1

                    while captcha_response is None and retries != 5:
                        self.logger.warning('Captcha not solved. Retrying captcha again...')
                        captcha_response = captcha_solver.solve_captcha()
                        retries += 1

                    if retries == 5 and captcha_response is None:
                        self.logger.error(f'2Captcha could not solve the captcha after {retries} attempts')
                    elif captcha_response == -1:
                        self.logger.error('Exiting after encountering an error with the captcha.')
                    else:
                        word = 'attempt' if retries == 1 else 'attempts'
                        self.logger.info(f'2Captcha successfully solved captcha after {retries} {word}')
                        # Set the captcha response
                        self.web_driver.execute_script(f'grecaptcha.getResponse = () => "{captcha_response}"')
                        self.web_driver.execute_script('validateLoginCaptcha()')

                    return 'CAPTCHA'

    def check_listing(self, listing_title):
        """Will check if a listing exists on the user's closet."""
        try:
            self.logger.info(f'Checking for "{listing_title}" listing')

            self.go_to_closet()

            if self.is_present(By.CLASS_NAME, 'tile__title'):
                titles = self.locate_all(By.CLASS_NAME, 'tile__title')
                for title in titles:
                    if listing_title in title.text:
                        self.logger.info(f'"{listing_title}" listing found')
                        return True

            self.logger.warning(f'"{listing_title}" listing not found')

            return False

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')

    def check_listing_timestamp(self, listing_title):
        """Given a listing title will check the last time the listing was shared"""
        try:
            self.logger.info(f'Checking the timestamp on following item: {listing_title}')

            self.go_to_closet()

            if self.check_listing(listing_title):
                listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                for listed_item in listed_items:
                    title = listed_item.find_element_by_class_name('tile__title')
                    if title.text == listing_title:
                        listing_button = listed_item.find_element_by_class_name('tile__covershot')
                        listing_button.click()

                        self.sleep(1)

                        timestamp_element = self.locate(
                            By.XPATH, '//*[@id="content"]/div/div/div[3]/div[2]/div[1]/div/header/div/div/div/div[2]'
                        )
                        timestamp = timestamp_element.text

                        timestamp = timestamp[8:]
                        elapsed_time = 9001
                        unit = 'DECADES'

                        space_index = timestamp.find(' ')

                        if timestamp == 'now':
                            elapsed_time = 0
                        elif timestamp[:space_index] == 'a':
                            elapsed_time = 60
                        elif timestamp[:space_index].isnumeric():
                            offset = space_index + 1
                            second_space_index = timestamp[offset:].find(' ') + offset
                            unit = timestamp[offset:second_space_index]

                            if unit == 'secs':
                                elapsed_time = int(timestamp[:space_index])
                            elif unit == 'mins':
                                elapsed_time = int(timestamp[:space_index]) * 60
                            elif unit == 'hours':
                                elapsed_time = int(timestamp[:space_index]) * 60 * 60

                        if elapsed_time > 25:
                            self.logger.error(f'Sharing does not seem to be working '
                                              f'Elapsed Time: {elapsed_time} {unit}')
                            return False
                        else:
                            self.logger.info(f'Shared successfully')

                            return True
            else:
                if self.check_inactive():
                    self.update_redis_object(self.redis_posh_user_id, {'status': PoshUser.INACTIVE})
                    return False

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')

    def check_inactive(self):
        """Will check if the current user is inactive"""
        try:
            self.logger.info(f'Checking is the following user is inactive: {self.get_redis_object_attr(self.redis_posh_user_id, "username")}')

            self.go_to_closet()

            listing_count_element = self.locate(
                By.XPATH, '//*[@id="content"]/div/div[1]/div/div[2]/div/div[2]/nav/ul/li[1]/a'
            )
            listing_count = listing_count_element.text
            index = listing_count.find('\n')
            total_listings = int(listing_count[:index])

            if total_listings > 0 and not self.is_present(By.CLASS_NAME, 'card--small'):
                self.logger.warning('This user does not seem to be active, setting inactive')
                self.update_redis_object(self.redis_posh_user_id, {'status': PoshUser.INACTIVE})
                return True
            else:
                self.logger.info('This user is still active')
                return False

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')

    def delete_listing(self, listing_title):
        """Given a listing title will delete the listing"""
        try:
            self.logger.info(f'Deleting the following item: {listing_title}')

            self.go_to_closet()

            if self.check_listing(listing_title):
                listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                for listed_item in listed_items:
                    title = listed_item.find_element_by_class_name('tile__title')
                    if title.text == listing_title:
                        listing_button = listed_item.find_element_by_class_name('tile__covershot')
                        listing_button.click()

                        self.sleep(1)

                        edit_listing_button = self.locate(By.XPATH, '//*[@id="content"]/div/div/div[3]/div[2]/div[1]/a')
                        edit_listing_button.click()

                        self.sleep(1, 2)

                        delete_listing_button = self.locate(
                            By.XPATH, '//*[@id="content"]/div/div[1]/div/div[2]/div/a[1]'
                        )
                        delete_listing_button.click()

                        self.sleep(1)

                        primary_buttons = self.locate_all(By.CLASS_NAME, 'btn--primary')
                        for primary_button in primary_buttons:
                            if primary_button.text == 'Yes':
                                primary_button.click()

                        self.sleep(5)

                        break
            else:
                self.logger.error('Could not find listing - It does not exist')

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')

    def check_logged_in(self):
        """Will go to the user's closet to see if the PoshUser is logged in or not, the bot knows if they are logged in
        if it can find the login button which is only displayed when a user is not logged in"""

        self.logger.info('Checking if user is signed in')
        self.web_driver.get(f'https://poshmark.com/closet/{self.get_redis_object_attr(self.redis_posh_user_id, "username")}')

        try:
            with open(f'/shared_volume/cookies/{self.get_redis_object_attr(self.redis_posh_user_id, "username")}.pkl', 'rb') as cookies:
                for cookie in pickle.load(cookies):
                    self.web_driver.add_cookie(cookie)
                self.web_driver.refresh()
                self.logger.info('Cookies loaded successfully')
        except FileNotFoundError:
            self.logger.warning('Cookies not loaded: Cookie file not found')

        result = self.is_present(By.XPATH, '//*[@id="app"]/header/nav[1]/div/ul/li[5]/div/div[1]/div')

        if result:
            self.logger.info('User is logged in')
            self.last_login = datetime.datetime.now()
            self.login_error = None
        else:
            self.logger.info('User is not logged in')

        return result

    def register(self):
        """Will register a given user to poshmark"""
        if int(self.get_redis_object_attr(self.redis_posh_user_id, 'is_registered')):
            pass
        else:
            try:
                self.logger.info(f'Registering {self.get_redis_object_attr(self.redis_posh_user_id, "username")}')
                self.web_driver.get('https://poshmark.com/signup')
                self.logger.info(f'At signup page - {self.web_driver.current_url}')

                # Get all fields for sign up
                first_name_field = self.locate(By.ID, 'firstName')
                last_name_field = self.locate(By.ID, 'lastName')
                email_field = self.locate(By.ID, 'email')
                username_field = self.locate(By.NAME, 'userName')
                password_field = self.locate(By.ID, 'password')
                gender_field = self.locate(By.CLASS_NAME, 'dropdown__selector--select-tag')

                # Send keys and select gender
                self.logger.info('Filling out form')
                first_name_field.send_keys(self.get_redis_object_attr(self.redis_posh_user_id, "first_name"))
                last_name_field.send_keys(self.get_redis_object_attr(self.redis_posh_user_id, "last_name"))
                email_field.send_keys(self.get_redis_object_attr(self.redis_posh_user_id, "email"))
                username_field.send_keys(self.get_redis_object_attr(self.redis_posh_user_id, "username"))
                password_field.send_keys(self.get_redis_object_attr(self.redis_posh_user_id, "password"))
                gender_field.click()
                self.sleep(1)
                gender_options = self.web_driver.find_elements_by_class_name('dropdown__link')
                done_button = self.locate(By.XPATH, '//button[@type="submit"]')

                gender = self.get_redis_object_attr(self.redis_posh_user_id, "gender")
                for element in gender_options:
                    if element.text == gender:
                        element.click()

                # Submit the form
                done_button.click()

                self.logger.info('Form submitted')

                error_code = self.check_for_errors()
                if error_code == 'CAPTCHA':
                    done_button = self.locate(By.XPATH, '//button[@type="submit"]')
                    done_button.click()
                    self.logger.info('Resubmitted form after entering captcha')

                    # Check if Posh User is now registered
                    attempts = 0
                    response = requests.get(f'https://poshmark.com/closet/{self.get_redis_object_attr(self.redis_posh_user_id, "username")}', proxies=self.requests_proxy)
                    while attempts < 5 and response.status_code != requests.codes.ok:
                        response = requests.get(f'https://poshmark.com/closet/{self.get_redis_object_attr(self.redis_posh_user_id, "username")}', proxies=self.requests_proxy)
                        self.logger.warning(
                            f'Closet for {self.get_redis_object_attr(self.redis_posh_user_id, "username")} is still not available - Trying again')
                        attempts += 1
                        self.sleep(5)

                    if response.status_code == requests.codes.ok:
                        self.update_redis_object(self.redis_posh_user_id, {'is_registered': 1})
                        self.logger.info(
                            f'Successfully registered {self.get_redis_object_attr(self.redis_posh_user_id, "username")}')

                        # Next Section - Profile
                        next_button = self.locate(By.XPATH, '//button[@type="submit"]')
                        next_button.click()

                        # Next Section - Select Brands (will not select brands)
                        self.sleep(1, 3)  # Sleep for realism
                        self.logger.info('Selecting random brands')
                        brands = self.web_driver.find_elements_by_class_name('content-grid-item')
                        next_button = self.locate(By.XPATH, '//button[@type="submit"]')

                        # Select random brands then click next
                        for x in range(random.randint(3, 5)):
                            try:
                                brand = random.choice(brands)
                                brand.click()
                            except IndexError:
                                pass
                        next_button.click()

                        # Next Section - All Done Page
                        self.sleep(1, 3)  # Sleep for realism
                        start_shopping_button = self.locate(By.XPATH, '//button[@type="submit"]')
                        start_shopping_button.click()

                        self.logger.info('Registration Complete')
                    else:
                        self.update_redis_object(self.redis_posh_user_id, {'is_registered': 0})
                        self.logger.info('Registration was not successful')
                elif error_code == 'ERROR_FORM_ERROR':
                    self.update_redis_object(self.redis_posh_user_id, {'status': PoshUser.INACTIVE})
                elif error_code is None:
                    # Check if Posh User is now registered
                    attempts = 0
                    response = requests.get(f'https://poshmark.com/closet/{self.get_redis_object_attr(self.redis_posh_user_id, "username")}', proxies=self.requests_proxy)
                    while attempts < 5 and response.status_code != requests.codes.ok:
                        response = requests.get(f'https://poshmark.com/closet/{self.get_redis_object_attr(self.redis_posh_user_id, "username")}', proxies=self.requests_proxy)
                        self.logger.warning(
                            f'Closet for {self.get_redis_object_attr(self.redis_posh_user_id, "username")} is still not available - Trying again')
                        attempts += 1
                        self.sleep(5)

                    if response.status_code == requests.codes.ok:
                        self.update_redis_object(self.redis_posh_user_id, {'is_registered': 1})
                        self.logger.info(
                            f'Successfully registered {self.get_redis_object_attr(self.redis_posh_user_id, "username")}')

                        # Next Section - Profile
                        next_button = self.locate(By.XPATH, '//button[@type="submit"]')
                        next_button.click()

                        # Next Section - Select Brands (will not select brands)
                        self.sleep(1, 3)  # Sleep for realism
                        self.logger.info('Selecting random brands')
                        brands = self.web_driver.find_elements_by_class_name('content-grid-item')
                        next_button = self.locate(By.XPATH, '//button[@type="submit"]')

                        # Select random brands then click next
                        for x in range(random.randint(3, 5)):
                            try:
                                brand = random.choice(brands)
                                brand.click()
                            except IndexError:
                                pass
                        next_button.click()

                        # Next Section - All Done Page
                        self.sleep(1, 3)  # Sleep for realism
                        start_shopping_button = self.locate(By.XPATH, '//button[@type="submit"]')
                        start_shopping_button.click()

                        self.logger.info('Registration Complete')
                    else:
                        self.update_redis_object(self.redis_posh_user_id, {'is_registered': 0})
                        self.logger.info('Registration was not successful')

            except Exception as e:
                self.logger.error(f'{traceback.format_exc()}')
                if not bool(self.get_redis_object_attr(self.redis_posh_user_id, 'is_registered')):
                    self.logger.error(f'User did not get registered')

    def log_in(self):
        """Will go to the Posh Mark home page and log in using waits for realism"""
        try:
            self.logger.info(f'Logging {self.get_redis_object_attr(self.redis_posh_user_id, "username")} in')

            self.web_driver.get('https://poshmark.com/login')

            attempts = 1
            while self.web_driver.current_url != 'https://poshmark.com/login' and attempts > 5:
                self.logger.warning(f'Could not go to log in page. Currently at {self.web_driver.current_url}. Trying again')
                self.web_driver.get('https://poshmark.com/login')
                attempts += 1

            if attempts >= 5:
                self.logger.error(f'Tried {attempts} times and could not go to log in page.')
                self.login_error = True

                return False

            self.logger.info(f'At login page - Current URL: {self.web_driver.current_url}')

            username_field = self.locate(By.ID, 'login_form_username_email')
            password_field = self.locate(By.ID, 'login_form_password')

            self.logger.info('Filling in form')

            username_field.send_keys(self.get_redis_object_attr(self.redis_posh_user_id, "username"))

            self.sleep(1)

            password_field.send_keys(self.get_redis_object_attr(self.redis_posh_user_id, "password"))
            password_field.send_keys(Keys.RETURN)

            self.logger.info('Form submitted')

            error_code = self.check_for_errors()

            if error_code == 'CAPTCHA':
                password_field = self.locate(By.ID, 'login_form_password')
                self.sleep(1)
                password_field.send_keys(Keys.RETURN)
                self.logger.info('Form resubmitted')

            self.last_login = datetime.datetime.now()
            self.login_error = None

            self.sleep(5)

            return True

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            self.login_error = True
            return False

    def go_to_closet(self):
        """Ensures the current url for the web driver is at users poshmark closet"""
        try:
            current_time = datetime.datetime.now()
            log_in_attempts = 0
            if self.last_login is None or self.last_login <= current_time - datetime.timedelta(hours=1) or self.login_error:
                if not self.check_logged_in():
                    while not self.log_in() and log_in_attempts < 2:
                        self.logger.warning('Could not log in, trying again.')
                        log_in_attempts += 1
                    if log_in_attempts >= 2:
                        self.update_redis_object(self.redis_campaign_id, {'status': '5'})
                        self.close()

            if self.web_driver.current_url != f'https://poshmark.com/closet/{self.get_redis_object_attr(self.redis_posh_user_id, "username")}':
                self.web_driver.get(f'https://poshmark.com/closet/{self.get_redis_object_attr(self.redis_posh_user_id, "username")}')
            else:
                self.logger.info(f"Already at {self.get_redis_object_attr(self.redis_posh_user_id, 'username')}'s closet, refreshing.")
                self.web_driver.refresh()

            show_all_listings_xpath = '//*[@id="content"]/div/div[2]/div/div/section/div[2]/div/div/button'
            if self.is_present(By.XPATH, show_all_listings_xpath):
                show_all_listings = self.locate(By.XPATH, show_all_listings_xpath)
                if show_all_listings.is_displayed():
                    show_all_listings.click()

            self.sleep(2)

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def get_all_listings(self):
        """Goes to a user's closet and returns a list of all the listings, excluding Ones that have an inventory tag"""
        try:
            shareable_listings = []
            sold_listings = []
            reserved_listings = []

            self.logger.info('Getting all listings')

            self.go_to_closet()

            if self.is_present(By.CLASS_NAME, 'card--small'):
                listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                for listed_item in listed_items:
                    title = listed_item.find_element_by_class_name('tile__title')
                    try:
                        icon = listed_item.find_element_by_class_name('inventory-tag__text')
                    except NoSuchElementException:
                        icon = None

                    if not icon:
                        shareable_listings.append(title.text)
                    elif icon.text == 'SOLD':
                        sold_listings.append(title.text)
                    elif icon.text == 'RESERVED':
                        reserved_listings.append(title.text)

                if shareable_listings:
                    self.logger.info(f"Found the following listings: {','.join(shareable_listings)}")
                else:
                    self.logger.info('No shareable listings found')

            else:
                if self.check_inactive():
                    self.update_redis_object(self.redis_posh_user_id, {'status': PoshUser.INACTIVE})

            listings = {
                'shareable_listings': shareable_listings,
                'sold_listings': sold_listings,
                'reserved_listings': reserved_listings
            }
            self.logger.debug(str(listings))
            return listings

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def update_profile(self):
        """Updates a user profile with their profile picture and header picture"""
        try:
            self.logger.info('Updating Profile')

            self.go_to_closet()

            edit_profile_button = self.locate(By.XPATH, '//a[@href="/user/edit-profile"]')
            edit_profile_button.click()

            self.logger.info('Clicked on edit profile button')

            self.sleep(2)

            # This while is to ensure that the profile picture path exists and tries 5 times
            attempts = 1
            profile_picture_path = self.get_redis_object_attr(self.redis_posh_user_id, 'profile_picture')
            profile_picture_exists = Path(profile_picture_path).is_file()
            while not profile_picture_exists and attempts < 6:
                self.logger.info(str(profile_picture_path))
                self.logger.warning(f'Could not find profile picture file. Attempt # {attempts}')
                self.sleep(2)
                profile_picture_exists = Path(profile_picture_path).is_file()
                attempts += 1
            else:
                if not profile_picture_exists:
                    self.logger.error('Could not upload profile picture - Picture not found.')
                else:
                    profile_picture = self.locate(By.XPATH,
                                                  '//*[@id="content"]/div/div[2]/div/div[1]/div[3]/label/input')
                    profile_picture.send_keys(profile_picture_path)

                    self.sleep(2)

                    apply_button = self.locate(
                        By.XPATH, '//*[@id="content"]/div/div[2]/div/div[1]/div[3]/div/div[2]/div[2]/div/button[2]')
                    apply_button.click()

                    self.logger.info('Profile picture uploaded')

                    self.sleep(2)

            attempts = 1
            header_picture_path = self.get_redis_object_attr(self.redis_posh_user_id, 'header_picture')
            header_picture_exists = Path(header_picture_path).is_file()
            while not header_picture_exists and attempts < 6:
                self.logger.info(str(header_picture_path))
                self.logger.warning(f'Could not find header picture file. Attempt # {attempts}')
                self.sleep(2)
                header_picture_exists = Path(header_picture_path).is_file()
                attempts += 1
            else:
                if not header_picture_exists:
                    self.logger.error('Could not upload header picture - Picture not found')
                else:
                    header_picture = self.locate(By.XPATH,
                                                 '//*[@id="content"]/div/div[2]/div/div[1]/div[2]/label/input')
                    header_picture.send_keys(header_picture_path)

                    self.sleep(2)

                    apply_button = self.locate(
                        By.XPATH, '//*[@id="content"]/div/div[2]/div/div[1]/div[2]/div/div[2]/div[2]/div/button[2]')
                    apply_button.click()

                    self.logger.info('Header picture uploaded')

                    self.sleep(2)

            save_button = self.locate(By.CLASS_NAME, 'btn--primary')
            save_button.click()

            self.logger.info('Profile saved')

            self.sleep(5)

            self.update_redis_object(self.redis_posh_user_id, {'profile_updated': 1})
        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def list_item(self, listing=None):
        """Will list an item on poshmark for the user"""
        try:
            if listing:
                self.logger.info(f'Listing the following item: {listing.title}')

                if not self.check_logged_in():
                    self.log_in()
            else:
                self.logger.info('Creating a fake listing')

                self.go_to_closet()

                if self.is_present(By.CLASS_NAME, 'card--small'):
                    listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                    for listed_item in listed_items:
                        title = listed_item.find_element_by_class_name('tile__title')
                        if '[FKE]' in title.text:
                            self.logger.info(f'The following fake listing already exists: {title.text}')
                            self.logger.info(f'Using this instead of making another')
                            return title.text

            self.web_driver.get('https://poshmark.com/create-listing')

            self.logger.info(f'Current URL: {self.web_driver.current_url}')

            self.sleep(2)

            if self.is_present(By.XPATH, '//*[@id="app"]/main/div[1]/div/div[2]'):
                self.logger.error('Error encountered when on the new listing page')
                if self.check_inactive():
                    self.update_redis_object(self.redis_posh_user_id, {'status': PoshUser.INACTIVE})
                else:
                    self.logger.info('User is not inactive')
            else:
                # Set category and sub category
                self.logger.info('Setting category')
                category_dropdown = self.locate(
                    By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/section[3]/div/div[2]/div[1]/div'
                )
                category_dropdown.click()

                space_index = listing.category.find(' ') if listing else ''
                primary_category = listing.category[:space_index] if listing else 'Men'
                secondary_category = listing.category[space_index + 1:] if listing else 'Pants'
                primary_categories = self.locate_all(By.CLASS_NAME, 'p--l--7')
                for category in primary_categories:
                    if category.text == primary_category:
                        category.click()
                        break

                secondary_categories = self.locate_all(By.CLASS_NAME, 'p--l--7')
                for category in secondary_categories[1:]:
                    if category.text == secondary_category:
                        category.click()
                        break

                self.logger.info('Category set')

                self.logger.info('Setting subcategory')

                subcategory_menu = self.locate(By.CLASS_NAME, 'dropdown__menu--expanded')
                subcategories = subcategory_menu.find_elements_by_tag_name('a')
                subcategory = listing.subcategory if listing else 'Dress'
                for available_subcategory in subcategories:
                    if available_subcategory.text == subcategory:
                        available_subcategory.click()
                        break

                self.logger.info('Subcategory set')

                # Set size (This must be done after the category has been selected)
                self.logger.info('Setting size')
                size_dropdown = self.locate(
                    By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/section[4]/div[2]/div[2]/div[1]/div[1]/div'
                )
                size_dropdown.click()
                size_buttons = self.locate_all(By.CLASS_NAME, 'navigation--horizontal__tab')

                for button in size_buttons:
                    if button.text == 'Custom':
                        button.click()
                        break

                custom_size_input = self.locate(By.ID, 'customSizeInput0')
                save_button = self.locate(
                    By.XPATH,
                    '//*[@id="content"]/div/div[1]/div[2]/section[4]/div[2]/div[2]/div[1]/div[2]/div/div/div[1]/ul/li/div/div/button'
                )
                done_button = self.locate(
                    By.XPATH,
                    '//*[@id="content"]/div/div[1]/div[2]/section[4]/div[2]/div[2]/div[1]/div[2]/div/div/div[2]/button'
                )
                size = listing.size if listing else 'Large'
                custom_size_input.send_keys(size)
                save_button.click()
                done_button.click()

                self.logger.info('Size set')

                # Upload listing photos, you have to upload the first picture then click apply before moving on to upload
                # the rest, otherwise errors come up.
                self.logger.info('Uploading photos')
                listing_photos = listing.get_photos() if listing else ['/static/poshmark/images/listing.jpg']
                upload_photos_field = self.locate(By.ID, 'img-file-input')
                upload_photos_field.send_keys(listing_photos[0])

                apply_button = self.locate(By.XPATH, '//*[@id="imagePlaceholder"]/div[2]/div[2]/div[2]/div/button[2]')
                apply_button.click()

                if len(listing_photos) > 1:
                    upload_photos_field = self.locate(By.ID, 'img-file-input')
                    for photo in listing_photos[1:]:
                        upload_photos_field.clear()
                        upload_photos_field.send_keys(photo)
                        self.sleep(1)

                self.logger.info('Photos uploaded')

                # Get all necessary fields
                self.logger.info('Putting in the rest of the field')
                title_field = self.locate(
                    By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/section[2]/div[1]/div[2]/div/div[1]/div/div/input'
                )
                description_field = self.locate(
                    By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/section[2]/div[2]/div[2]/textarea'
                )
                brand_field = self.locate(
                    By.XPATH,
                    '/html/body/div[1]/main/div[2]/div/div[1]/div/section[6]/div/div[2]/div[1]/div[1]/div/input'
                )

                input_fields = self.locate_all(By.TAG_NAME, 'input')
                for input_field in input_fields:
                    if input_field.get_attribute('data-vv-name') == 'originalPrice':
                        original_price_field = input_field
                    if input_field.get_attribute('data-vv-name') == 'listingPrice':
                        listing_price_field = input_field

                # Send all the information to their respected fields
                lowercase = string.ascii_lowercase
                uppercase = string.ascii_uppercase
                title = listing.title if listing else f"{uppercase[0]}{''.join([random.choice(lowercase) for i in range(7)])} [FKE] {''.join([random.choice(lowercase) for i in range(5)])}"
                title_field.send_keys(title)

                description = listing.description if listing else f"{uppercase[0]}{''.join([random.choice(lowercase) for i in range(7)])} {''.join([random.choice(lowercase) for i in range(5)])} {''.join([random.choice(lowercase) for i in range(5)])}"

                for part in description.split('\n'):
                    description_field.send_keys(part)
                    ActionChains(self.web_driver).key_down(Keys.SHIFT).key_down(Keys.ENTER).key_up(Keys.SHIFT).key_up(
                        Keys.ENTER).perform()

                original_prize = str(listing.original_price) if listing else '35'
                original_price_field.send_keys(original_prize)
                listing_price = str(listing.listing_price) if listing else '25'
                listing_price_field.send_keys(listing_price)
                brand = listing.brand if listing else 'Saks Fifth Avenue'
                brand_field.send_keys(brand)

                if listing:
                    if listing.tags:
                        tags_button = self.locate(
                            By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/section[5]/div/div[2]/div[1]/button[1]',
                            'clickable'
                        )
                        self.web_driver.execute_script("arguments[0].click();", tags_button)

                next_button = self.locate(By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/div[2]/button')
                next_button.click()

                self.sleep(1)

                list_item_button = self.locate(
                    By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/div[3]/div[2]/div[2]/div[2]/button'
                )
                list_item_button.click()

                sell_button = self.is_present(By.XPATH, '//*[@id="app"]/header/nav[2]/div[1]/ul[2]/li[2]/a')

                attempts = 0

                while not sell_button and attempts <= 10:
                    self.logger.error('Not done listing item. Checking again...')
                    sell_button = self.is_present(By.XPATH, '//*[@id="app"]/header/nav[2]/div[1]/ul[2]/li[2]/a')
                    attempts += 1
                else:
                    if attempts > 10:
                        self.logger.error(f'Attempted to locate the sell button {attempts} times but could not find it.')
                    else:
                        self.logger.info('Item listed successfully')

                return title

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def update_listing(self, current_title, redis_listing_id, brand=None):
        """Will update the listing with the current title with all of the information for the listing that was passed,
        if a brand is given it will update the brand to that otherwise it will use the listings brand"""
        try:
            listing_title = self.get_redis_object_attr(redis_listing_id, 'title')
            listing_brand = self.get_redis_object_attr(redis_listing_id, 'brand')
            listing_category = self.get_redis_object_attr(redis_listing_id, 'category')
            listing_subcategory = self.get_redis_object_attr(redis_listing_id, 'subcategory')
            listing_size = self.get_redis_object_attr(redis_listing_id, 'size')
            listing_cover_photo = self.get_redis_object_attr(redis_listing_id, 'cover_photo')
            listing_description = self.get_redis_object_attr(redis_listing_id, 'description')
            listing_tags = int(self.get_redis_object_attr(redis_listing_id, 'tags'))
            listing_original_price = self.get_redis_object_attr(redis_listing_id, 'original_price')
            listing_listing_price = self.get_redis_object_attr(redis_listing_id, 'listing_price')
            listing_photos = self.get_redis_object_attr(self.get_redis_object_attr(redis_listing_id, 'photos'))
            self.logger.info(f'Updating the following item: {current_title}')

            self.go_to_closet()

            if self.check_listing(current_title):
                listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                for listed_item in listed_items:
                    title = listed_item.find_element_by_class_name('tile__title')
                    if title.text == current_title:
                        listing_button = listed_item.find_element_by_class_name('tile__covershot')
                        listing_button.click()

                        self.sleep(3)

                        edit_listing_button = self.locate(By.XPATH, '//*[@id="content"]/div/div/div[3]/div[2]/div[1]/a')
                        edit_listing_button.click()

                        self.sleep(5)

                        if brand:
                            brand_field = self.locate(
                                By.XPATH,
                                '//*[@id="content"]/div/div[1]/div/section[6]/div/div[2]/div[1]/div[1]/div/input'
                            )

                            brand_field.clear()
                            brand_field.send_keys(listing_brand)

                            self.web_driver.execute_script("window.scrollTo(0, 3000);")

                            availability = self.locate(By.XPATH, '//*[@id="content"]/div/div[1]/div/section[10]/div/div[2]/div/div')
                            availability.click()

                            availability_selections = self.locate_all(By.CLASS_NAME, 'dropdown__link')
                            for availability_selection in availability_selections:
                                if availability_selection.text == 'For Sale':
                                    availability_selection.click()

                            time.sleep(5)
                        else:
                            self.web_driver.execute_script("window.scrollTo(0, 1280);")

                            # Update Category and Sub Category
                            self.logger.info('Updating category')
                            category_dropdown = self.locate(
                                By.XPATH,
                                '//*[@id="content"]/div/div[1]/div/section[3]/div/div[2]/div[1]/div/div[1]'

                            )
                            category_dropdown.click()

                            space_index = listing_category.find(' ')
                            primary_category = listing_category[:space_index]
                            secondary_category = listing_category[space_index + 1:]
                            primary_categories = self.locate_all(By.CLASS_NAME, 'p--l--7')
                            for category in primary_categories:
                                if category.text == primary_category:
                                    category.click()
                                    break

                            secondary_categories = self.locate_all(By.CLASS_NAME, 'p--l--7')
                            for category in secondary_categories[1:]:
                                if category.text == secondary_category:
                                    category.click()
                                    break

                            self.logger.info('Category Updated')

                            self.logger.info('Updating subcategory')

                            subcategory_menu = self.locate(By.CLASS_NAME, 'dropdown__menu--expanded')
                            subcategories = subcategory_menu.find_elements_by_tag_name('a')
                            subcategory = listing_subcategory
                            for available_subcategory in subcategories:
                                if available_subcategory.text == subcategory:
                                    available_subcategory.click()
                                    break

                            self.logger.info('Subcategory updated')

                            # Set size (This must be done after the category has been selected)
                            self.logger.info('Updating size')
                            size_dropdown = self.locate(
                                By.XPATH, '//*[@id="content"]/div/div[1]/div/section[4]/div[2]/div[2]/div[1]/div[1]/div'
                            )
                            size_dropdown.click()
                            size_buttons = self.locate_all(By.CLASS_NAME, 'navigation--horizontal__tab')

                            for button in size_buttons:
                                if button.text == 'Custom':
                                    button.click()
                                    break

                            custom_size_input = self.locate(By.ID, 'customSizeInput0')
                            save_button = self.locate(
                                By.XPATH,
                                '//*[@id="content"]/div/div[1]/div/section[4]/div[2]/div[2]/div[1]/div[2]/div/div/div[1]/ul/li/div/div/button'
                            )
                            done_button = self.locate(
                                By.XPATH,
                                '//*[@id="content"]/div/div[1]/div/section[4]/div[2]/div[2]/div[1]/div[2]/div/div/div[2]/button'
                            )
                            size = listing_size
                            custom_size_input.send_keys(size)
                            save_button.click()
                            done_button.click()

                            self.logger.info('Size updated')

                            # Update photos
                            self.logger.info('Uploading photos')

                            cover_photo = self.locate(By.XPATH,
                                                      '//*[@id="imagePlaceholder"]/div/div/label/div[1]/div/div')
                            cover_photo.click()

                            cover_photo_field = self.locate(
                                By.XPATH,
                                '//*[@id="imagePlaceholder"]/div[2]/div[2]/div[1]/div/div/div/div[2]/div/span/label/input'
                            )
                            cover_photo_field.send_keys(listing_cover_photo)

                            self.sleep(1)

                            apply_button = self.locate(
                                By.XPATH,
                                '//*[@id="imagePlaceholder"]/div[2]/div[2]/div[2]/div/button[2]'
                            )
                            apply_button.click()

                            self.sleep(1)

                            for photo in listing_photos:
                                upload_photos_field = self.locate(By.ID, 'img-file-input')
                                upload_photos_field.clear()
                                upload_photos_field.send_keys(photo)
                                self.sleep(1)

                            self.logger.info('Photos uploaded')

                            # Get all necessary fields
                            self.logger.info('Updating the rest of the fields')
                            title_field = self.locate(
                                By.XPATH,
                                '//*[@id="content"]/div/div[1]/div/section[2]/div[1]/div[2]/div/div[1]/div/div/input'
                            )
                            description_field = self.locate(
                                By.XPATH, '//*[@id="content"]/div/div[1]/div/section[2]/div[2]/div[2]/textarea'
                            )

                            input_fields = self.locate_all(By.TAG_NAME, 'input')
                            for input_field in input_fields:
                                if input_field.get_attribute('data-vv-name') == 'originalPrice':
                                    original_price_field = input_field
                                if input_field.get_attribute('data-vv-name') == 'listingPrice':
                                    listing_price_field = input_field

                            # Send all the information to their respected fields
                            title_field.clear()
                            title_field.send_keys(listing_title)

                            description_field.clear()
                            for part in listing_description.split('\n'):
                                description_field.send_keys(part)
                                ActionChains(self.web_driver).key_down(Keys.SHIFT).key_down(Keys.ENTER).key_up(
                                    Keys.SHIFT).key_up(
                                    Keys.ENTER).perform()

                            original_prize = str(listing_original_price)
                            original_price_field.clear()
                            original_price_field.send_keys(original_prize)
                            listing_price = str(listing_listing_price)
                            listing_price_field.clear()
                            listing_price_field.send_keys(listing_price)

                            if listing_tags:
                                tags_button = self.locate(
                                    By.XPATH,
                                    '//*[@id="content"]/div/div[1]/div/section[5]/div/div[2]/div[1]/button[1]',
                                    'clickable'
                                )
                                self.web_driver.execute_script("arguments[0].click();", tags_button)

                        update_button = self.locate(By.XPATH, '//*[@id="content"]/div/div[1]/div/div[2]/button')
                        update_button.click()

                        self.sleep(1)

                        list_item_button = self.locate(
                            By.XPATH, '//*[@id="content"]/div/div[1]/div/div[3]/div[2]/div[2]/div[2]/button'
                        )
                        list_item_button.click()

                        sell_button = self.is_present(By.XPATH, '//*[@id="app"]/header/nav[2]/div[1]/ul[2]/li[2]/a')

                        attempts = 0

                        while not sell_button and attempts <= 10:
                            self.logger.error('Not done updating listing. Checking again...')
                            sell_button = self.is_present(By.XPATH, '//*[@id="app"]/header/nav[2]/div[1]/ul[2]/li[2]/a')
                            attempts += 1
                        else:
                            if attempts > 10:
                                self.logger.error(f'Attempted to locate the sell button {attempts} times but could not find it.')
                            else:
                                self.logger.info('Updated successfully')

                        break
            else:
                if self.check_inactive():
                    self.logger.warning('Setting user status to inactive')
                    self.update_redis_object(self.redis_posh_user_id, {'status': PoshUser.INACTIVE})

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def share_item(self, listing_title):
        """Will share an item in the closet"""
        try:
            self.logger.info(f'Sharing the following item: {listing_title}')

            self.go_to_closet()

            if self.check_listing(listing_title):
                listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                for listed_item in listed_items:
                    title = listed_item.find_element_by_class_name('tile__title')
                    if title.text == listing_title:
                        share_button = listed_item.find_element_by_class_name('social-action-bar__share')
                        share_button.click()

                        self.sleep(1)

                        to_followers_button = self.locate(By.CLASS_NAME, 'internal-share__link')
                        to_followers_button.click()

                        self.logger.info('Item Shared')

                        return self.check_listing_timestamp(listing_title)

            else:
                if self.check_inactive():
                    self.logger.warning('Setting user status to inactive')
                    self.update_redis_object(self.redis_posh_user_id, {'status': PoshUser.INACTIVE})

                    return False

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def check_news(self):
        """If the PoshUser is logged in it will check their new else it will log them in then check their news"""
        if not self.check_logged_in():
            self.log_in()
        else:
            badge = self.locate(By.CLASS_NAME, 'badge badge--red badge--right')
            if badge:
                news_nav = self.locate(By.XPATH, '//a[@href="/news"]')
                news_nav.click()

    def check_offers(self, redis_listing_id=None, listing_title=None):
        try:
            listing_title = self.get_redis_object_attr(redis_listing_id, 'title') if redis_listing_id else listing_title
            lowest_price = int(self.get_redis_object_attr(redis_listing_id, 'lowest_price')) if redis_listing_id else int(self.get_redis_object_attr(self.redis_campaign_id, 'lowest_price'))
            self.logger.info(f'Checking offers for {listing_title}')
            self.web_driver.get('https://poshmark.com/offers/my_offers')

            if self.is_present(By.CLASS_NAME, 'active-offers__content'):
                offers = self.locate_all(By.CLASS_NAME, 'active-offers__content')

                for offer in offers:
                    if listing_title in offer.text:
                        self.logger.info('Offers found')
                        offer.click()

                        listing_price_text = self.locate(By.XPATH, '//*[@id="content"]/div/div[2]/div[2]/div[1]/div/div[2]/h5[2]').text
                        listing_price = int(re.findall(r'\d+', listing_price_text)[-1])

                        active_offers = self.locate_all(By.CLASS_NAME, 'active-offers__content')
                        offer_page_url = self.web_driver.current_url

                        self.logger.info(f'There are currently {len(active_offers)} active offers')
                        for x in range(len(active_offers)):
                            active_offers = self.locate_all(By.CLASS_NAME, 'active-offers__content')
                            active_offer = active_offers[x]
                            active_offer.click()

                            self.sleep(2)
                            try:
                                self.locate_all(By.CLASS_NAME, 'btn--primary')

                                sender_offer = 0
                                receiver_offer = 0
                                chat_bubbles = self.locate_all(By.CLASS_NAME, 'ai--fs')
                                for chat_bubble in reversed(chat_bubbles):
                                    try:
                                        bubble = chat_bubble.find_element_by_xpath('.//*')
                                        if sender_offer and receiver_offer:
                                            break
                                        elif 'sender' in bubble.get_attribute('class') and not sender_offer:
                                            text = bubble.text
                                            if 'offered' in text:
                                                sender_offer = int(re.findall(r'\d+', text)[-1])
                                            elif 'cancelled' in text:
                                                self.logger.warning(f'Seller cancelled. Message: "{text}"')
                                                break
                                            else:
                                                self.logger.warning(f'Unknown message sent by seller. Message: "{text}"')
                                                break
                                        elif 'receiver' in bubble.get_attribute('class') and not receiver_offer:
                                            text = bubble.text
                                            if 'declined' in text:
                                                receiver_offer = listing_price
                                            elif 'offered' or 'listed' in text:
                                                receiver_offer = int(re.findall(r'\d+', text)[-1])
                                            else:
                                                self.logger.warning(f'Unknown message sent by seller. Message: "{text}"')
                                                break
                                    except NoSuchElementException:
                                        pass

                                if sender_offer:
                                    if sender_offer >= lowest_price or sender_offer >= receiver_offer - 1:
                                        primary_buttons = self.locate_all(By.CLASS_NAME, 'btn--primary')
                                        for button in primary_buttons:
                                            if button.text == 'Accept':
                                                button.click()
                                                break

                                        self.sleep(2)

                                        primary_buttons = self.locate_all(By.CLASS_NAME, 'btn--primary')
                                        for button in primary_buttons:
                                            if button.text == 'Yes':
                                                button.click()
                                                self.logger.info(f'Accepted offer at ${sender_offer}.')
                                                self.sleep(5)
                                                break
                                    else:
                                        secondary_buttons = self.locate_all(By.CLASS_NAME, 'btn--tertiary')

                                        if receiver_offer < lowest_price - 4:
                                            for button in secondary_buttons:
                                                if button.text == 'Decline':
                                                    button.click()
                                                    break

                                            self.sleep(1)
                                            primary_buttons = self.locate_all(By.CLASS_NAME, 'btn--primary')
                                            for button in primary_buttons:
                                                if button.text == 'Yes':
                                                    button.click()
                                                    self.sleep(5)
                                                    break
                                        else:
                                            for button in secondary_buttons:
                                                if button.text == 'Counter':
                                                    button.click()
                                                    break
                                            if receiver_offer <= lowest_price:
                                                new_offer = receiver_offer - 1
                                            else:
                                                new_offer = round(receiver_offer - (receiver_offer * .05))
                                                if new_offer < lowest_price:
                                                    new_offer = lowest_price

                                            counter_offer = new_offer

                                            counter_offer_input = self.locate(By.CLASS_NAME, 'form__text--input')
                                            counter_offer_input.send_keys(str(counter_offer))
                                            self.sleep(2)
                                            primary_buttons = self.locate_all(By.CLASS_NAME, 'btn--primary')
                                            for button in primary_buttons:
                                                if button.text == 'Submit':
                                                    button.click()
                                                    self.logger.info(f'Buyer offered ${sender_offer}, countered offer sent for ${counter_offer}')
                                                    self.sleep(5)
                                                    break
                                else:
                                    self.logger.warning('Nothing to do on the current offer')
                                    self.logger.debug(f'Our Offer: ${receiver_offer} Sender Offer: ${sender_offer}')
                            except TimeoutException:
                                self.logger.warning('Nothing to do on the current offer, seems buyer has not counter offered.')
                            self.web_driver.get(offer_page_url)
            else:
                self.logger.warning('No offers at the moment')

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def send_offer_to_likers(self, redis_listing_id=None, listing_title=None):
        """Will send offers to all likers for a given listing"""
        try:
            listing_title = self.get_redis_object_attr(redis_listing_id, 'title') if redis_listing_id else listing_title
            lowest_price = int(self.get_redis_object_attr(redis_listing_id, 'lowest_price')) if redis_listing_id else int(self.get_redis_object_attr(self.redis_campaign_id, 'lowest_price'))
            self.logger.info(f'Sending offers to all likers for the following item: {listing_title}')

            self.go_to_closet()

            if self.check_listing(listing_title):
                listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                for listed_item in listed_items:
                    title = listed_item.find_element_by_class_name('tile__title')
                    if title.text == listing_title:
                        listing_price_text = listed_item.find_element_by_class_name('fw--bold').text
                        listing_price = int(re.findall(r'\d+', listing_price_text)[-1])

                        listing_button = listed_item.find_element_by_class_name('tile__covershot')
                        listing_button.click()

                        self.sleep(2)

                        offer_button = self.locate(
                            By.XPATH, '//*[@id="content"]/div/div/div[3]/div[2]/div[5]/div[2]/div/div/button'
                        )
                        offer_button.click()

                        offer_to_likers_button = self.locate(By.XPATH, '//*[@id="content"]/div/div/div[3]/div[2]/div[5]/div[2]/div/div[2]/div[1]/div[2]/div[2]/div/div[2]/div/button')
                        offer_to_likers_button.click()

                        self.sleep(1)

                        offer = round(lowest_price + (lowest_price * .05))
                        ten_off = int(listing_price - (listing_price * .1))
                        if offer > ten_off:
                            offer = ten_off

                        self.logger.info(f'Sending offers to likers for ${offer}')

                        offer_input = self.locate(By.XPATH, '//*[@id="content"]/div/div/div[3]/div[2]/div[5]/div[2]/div/div[2]/div[1]/div[2]/div[2]/div/form/div[1]/input')
                        offer_input.send_keys(str(offer))

                        self.sleep(2)

                        shipping_dropdown = self.locate(By.XPATH, '//*[@id="content"]/div/div/div[3]/div[2]/div[5]/div[2]/div/div[2]/div[1]/div[2]/div[2]/div/form/div[2]/div[1]/div/div/div/div[1]/div')
                        shipping_dropdown.click()

                        shipping_options = self.locate_all(By.CLASS_NAME, 'dropdown__menu__item')

                        for shipping_option in shipping_options:
                            if shipping_option.text == 'FREE':
                                shipping_option.click()
                                break

                        apply_button = self.locate(By.XPATH, '//*[@id="content"]/div/div/div[3]/div[2]/div[5]/div[2]/div/div[2]/div[1]/div[2]/div[3]/div/button[2]')
                        apply_button.click()

                        done_button = self.locate(By.XPATH, '//*[@id="content"]/div/div/div[3]/div[2]/div[5]/div[2]/div/div[2]/div[2]/div[3]/button')
                        done_button.click()

                        self.logger.info('Offers successfully sent!')

                        return True
            else:
                self.logger.warning(f'The following listing was not found: {listing_title}')
                self.logger.warning(f'Offers not sent to likers')

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def check_comments(self, listing_title):
        """Checks all the comments for a given listing to ensure there are no bad comments, if so it reports them"""
        try:
            self.logger.info(f'Checking the comments for the following item: {listing_title}')

            self.go_to_closet()

            bad_words = ('scam', 'scammer', 'fake', 'replica', 'reported', 'counterfeit', 'stolen')
            reported = False

            if self.check_listing(listing_title):
                listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                for listed_item in listed_items:
                    title = listed_item.find_element_by_class_name('tile__title')
                    if title.text == listing_title:
                        listing_button = listed_item.find_element_by_class_name('tile__covershot')
                        listing_button.click()

                        self.sleep(3)
                        if self.is_present(By.CLASS_NAME, 'comment-item__container'):
                            regex = re.compile('[^a-zA-Z]+')
                            comments = self.locate_all(By.CLASS_NAME, 'comment-item__container')
                            for comment in comments:
                                text = comment.find_element_by_class_name('comment-item__text').text
                                cleaned_comment = regex.sub('', text.lower())

                                if any([bad_word in cleaned_comment for bad_word in bad_words]):
                                    report_button = comment.find_element_by_class_name('flag')
                                    report_button.click()

                                    self.sleep(1)

                                    primary_buttons = self.locate_all(By.CLASS_NAME, 'btn--primary')
                                    for button in primary_buttons:
                                        if button.text == 'Submit':
                                            button.click()
                                            reported = True
                                            self.logger.warning(f'Reported the following comment as spam: {text}')
                                            break
                            if not reported:
                                self.logger.info(f'No comments with the following words: {", ".join(bad_words)}')
                        else:
                            self.logger.info(f'No comments on this listing yet.')
                        break

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def check_ip(self, filename=None):
        self.web_driver.get('https://www.whatsmyip.org/')
        host_name = self.locate(By.ID, 'hostname')

        self.logger.debug(f'Hostname: {host_name.text}')