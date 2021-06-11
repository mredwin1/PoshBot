import datetime
import os
import random
import re
import requests
import time
import traceback
import string

from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CAPTCHA_API_KEY = os.environ['CAPTCHA_API_KEY']


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


class PoshMarkClient:
    def __init__(self, posh_user, campaign, logger, posh_proxy=None):
        proxy = Proxy()
        hostname = posh_proxy.ip if posh_proxy else ''
        port = posh_proxy.port if posh_proxy else ''
        proxy.proxy_type = ProxyType.MANUAL if posh_proxy else ProxyType.SYSTEM

        if posh_proxy:
            proxy.http_proxy = '{hostname}:{port}'.format(hostname=hostname, port=port)
            proxy.ssl_proxy = '{hostname}:{port}'.format(hostname=hostname, port=port)

        capabilities = webdriver.DesiredCapabilities.CHROME
        proxy.add_to_capabilities(capabilities)

        self.posh_user = posh_user
        self.campaign = campaign
        self.last_login = None
        self.login_error = None
        self.logger = logger
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

    def __enter__(self):
        self.open()

        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def open(self):
        """Used to open the selenium web driver session"""
        self.web_driver = webdriver.Chrome('/poshmark/poshmark_client/chromedriver', options=self.web_driver_options)
        self.web_driver.implicitly_wait(10)
        if '--headless' in self.web_driver_options.arguments:
            self.web_driver.set_window_size(1920, 1080)

    def close(self):
        """Closes the selenium web driver session"""
        self.web_driver.quit()

    def locate(self, by, locator, location_type=None):
        """Locates the first elements with the given By"""
        wait = WebDriverWait(self.web_driver, 20)
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
        wait = WebDriverWait(self.web_driver, 20)
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
                    self.posh_user.status = '2'
                    self.posh_user.save()

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
                    self.posh_user.status = '2'
                    self.posh_user.save()
                    return False

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')

    def check_inactive(self):
        """Will check if the current user is inactive"""
        try:
            self.logger.info(f'Checking is the following user is inactive: {self.posh_user.username}')

            self.go_to_closet()

            listing_count_element = self.locate(
                By.XPATH, '//*[@id="content"]/div/div[1]/div/div[2]/div/div[2]/nav/ul/li[1]/a'
            )
            listing_count = listing_count_element.text
            index = listing_count.find('\n')
            total_listings = int(listing_count[:index])

            if total_listings > 0 and not self.is_present(By.CLASS_NAME, 'card--small'):
                self.logger.warning('This user does not seem to be active, setting inactive')
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
        self.web_driver.get(f'https://poshmark.com/closet/{self.posh_user.username}')
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
        if self.posh_user.is_registered:
            pass
        else:
            previous_status = self.posh_user.status
            try:
                self.logger.info(f'Registering {self.posh_user.username}')
                self.posh_user.status = '4'
                self.posh_user.save()
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
                first_name_field.send_keys(self.posh_user.first_name)
                last_name_field.send_keys(self.posh_user.last_name)
                email_field.send_keys(self.posh_user.email)
                username_field.send_keys(self.posh_user.username)
                password_field.send_keys(self.posh_user.password)
                gender_field.click()
                self.sleep(1)
                gender_options = self.web_driver.find_elements_by_class_name('dropdown__link')
                done_button = self.locate(By.XPATH, '//button[@type="submit"]')

                gender = self.posh_user.get_gender()
                for element in gender_options:
                    if element.text == gender:
                        element.click()

                # Submit the form
                done_button.click()

                self.logger.info('Form submitted')

                self.sleep(5)

                error_code = self.check_for_errors()
                if error_code == 'CAPTCHA':
                    done_button = self.locate(By.XPATH, '//button[@type="submit"]')
                    done_button.click()
                    self.logger.info('Resubmitted form after entering captcha')

                    self.web_driver.save_screenshot('/media/register.png')

                    # Check if Posh User is now registered
                    attempts = 0
                    response = requests.get(f'https://poshmark.com/closet/{self.posh_user.username}')
                    while attempts < 5 and response.status_code != requests.codes.ok:
                        response = requests.get(f'https://poshmark.com/closet/{self.posh_user.username}')
                        self.logger.warning(
                            f'Closet for {self.posh_user.username} is still not available - Trying again')
                        attempts += 1
                        self.sleep(5)

                    if response.status_code == requests.codes.ok:
                        self.posh_user.is_registered = True
                        self.posh_user.status = '1'
                        self.posh_user.save()
                        self.logger.info(
                            f'Successfully registered {self.posh_user.username}, status changed to "Active"')

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
                        self.posh_user.status = previous_status
                        self.posh_user.save()
                        self.logger.error(
                            f'Closet could not be found at https://poshmark.com/closet/{self.posh_user.username}')
                        self.logger.error('Status changed to previous status')
                elif error_code == 'ERROR_FORM_ERROR':
                    self.posh_user.status = '2'
                    self.posh_user.save()
                elif error_code is None:
                    # Check if Posh User is now registered
                    attempts = 0
                    response = requests.get(f'https://poshmark.com/closet/{self.posh_user.username}')
                    while attempts < 5 and response.status_code != requests.codes.ok:
                        response = requests.get(f'https://poshmark.com/closet/{self.posh_user.username}')
                        self.logger.warning(
                            f'Closet for {self.posh_user.username} is still not available - Trying again')
                        attempts += 1
                        self.sleep(5)

                    if response.status_code == requests.codes.ok:
                        self.posh_user.is_registered = True
                        self.posh_user.status = '1'
                        self.posh_user.save()
                        self.logger.info(
                            f'Successfully registered {self.posh_user.username}, status changed to "Active"')

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
                        self.posh_user.is_registered = False
                        self.posh_user.status = '0'
                        self.posh_user.save()
                        self.logger.info('Registration was not successful')

            except Exception as e:
                self.logger.error(f'{traceback.format_exc()}')
                if not self.posh_user.is_registered:
                    self.logger.error(f'User did not get registered - Changing status back to {previous_status}')
                    self.posh_user.status = previous_status
                    self.posh_user.save()

    def log_in(self):
        """Will go to the Posh Mark home page and log in using waits for realism"""
        try:
            self.logger.info(f'Logging {self.posh_user.username} in')

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

            username_field.send_keys(self.posh_user.username)

            self.sleep(1)

            password_field.send_keys(self.posh_user.password)
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
                        self.campaign.refresh_from_db()
                        self.campaign.status = '5'
                        self.campaign.save()
                        self.close()

            if self.web_driver.current_url != f'https://poshmark.com/closet/{self.posh_user.username}':
                self.web_driver.get(f'https://poshmark.com/closet/{self.posh_user.username}')
            else:
                self.logger.info(f"Already at {self.posh_user.username}'s closet, refreshing.")
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
                    self.posh_user.status = '2'
                    self.posh_user.save()

            listings = {
                'shareable_listings': shareable_listings,
                'sold_listings': sold_listings,
                'reserved_listings': reserved_listings
            }
            self.logger.debug(listings)
            return listings

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def update_profile(self):
        """Updates a user profile with their profile picture and header picture"""
        previous_status = self.posh_user.status
        try:
            self.logger.info('Updating Profile')
            self.posh_user.status = '5'
            self.posh_user.save()

            self.go_to_closet()

            edit_profile_button = self.locate(By.XPATH, '//a[@href="/user/edit-profile"]')
            edit_profile_button.click()

            self.logger.info('Clicked on edit profile button')

            self.sleep(2)

            # This while is to ensure that the profile picture path exists and tries 5 times
            attempts = 1
            profile_picture_path = self.posh_user.profile_picture.path
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
            header_picture_path = self.posh_user.header_picture.path
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

            self.posh_user.status = '1'
            self.posh_user.save()

            self.logger.info('Posh User status changed to "Active"')
        except Exception as e:
            self.logger.error(f'Error encountered - Changing status back to {previous_status}')
            self.logger.error(f'{traceback.format_exc()}')

            self.posh_user.status = previous_status
            self.posh_user.save()

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
                    self.posh_user.status = '2'
                    self.posh_user.save()
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

    def update_listing(self, current_title, listing):
        """Will update the listing with the current title with all of the information for the listing that was passed,
        if a brand is given it will update the brand to that otherwise it will use the listings brand"""
        try:
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

                        self.web_driver.execute_script("window.scrollTo(0, 1280);")

                        # Update Category and Sub Category
                        self.logger.info('Updating category')
                        category_dropdown = self.locate(
                            By.XPATH,
                            '//*[@id="content"]/div/div[1]/div/section[3]/div/div[2]/div[1]/div/div[1]'

                        )
                        category_dropdown.click()

                        space_index = listing.category.find(' ')
                        primary_category = listing.category[:space_index]
                        secondary_category = listing.category[space_index + 1:]
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
                        subcategory = listing.subcategory
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
                        size = listing.size
                        custom_size_input.send_keys(size)
                        save_button.click()
                        done_button.click()

                        self.logger.info('Size updated')

                        # Update photos
                        self.logger.info('Uploading photos')
                        listing_photos = listing.get_photos()

                        cover_photo = self.locate(By.XPATH,
                                                  '//*[@id="imagePlaceholder"]/div/div/label/div[1]/div/div')
                        cover_photo.click()

                        cover_photo_field = self.locate(
                            By.XPATH,
                            '//*[@id="imagePlaceholder"]/div[2]/div[2]/div[1]/div/div/div/div[2]/div/span/label/input'
                        )
                        cover_photo_field.send_keys(listing.cover_photo.path)

                        self.sleep(1)

                        apply_button = self.locate(
                            By.XPATH,
                            '//*[@id="imagePlaceholder"]/div[2]/div[2]/div[2]/div/button[2]'
                        )
                        apply_button.click()

                        self.sleep(1)

                        if len(listing_photos) > 1:
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
                        brand_field = self.locate(
                            By.XPATH,
                            '//*[@id="content"]/div/div[1]/div/section[6]/div/div[2]/div[1]/div[1]/div/input'
                        )

                        # Send all the information to their respected fields
                        title_field.clear()
                        title_field.send_keys(listing.title)

                        description_field.clear()
                        for part in listing.description.split('\n'):
                            description_field.send_keys(part)
                            ActionChains(self.web_driver).key_down(Keys.SHIFT).key_down(Keys.ENTER).key_up(
                                Keys.SHIFT).key_up(
                                Keys.ENTER).perform()

                        original_prize = str(listing.original_price)
                        original_price_field.clear()
                        original_price_field.send_keys(original_prize)
                        listing_price = str(listing.listing_price)
                        listing_price_field.clear()
                        listing_price_field.send_keys(listing_price)
                        brand_field.clear()
                        brand_field.send_keys(listing.brand)

                        if listing.tags:
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
                    self.posh_user.status = '2'
                    self.posh_user.save()

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')

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
                    self.posh_user.status = '2'
                    self.posh_user.save()
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

    def check_offers(self, listing=None, listing_title=None):
        try:
            listing_title = listing.title if listing else listing_title
            lowest_price = listing.lowest_price if listing else self.campaign.lowest_price
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

    def send_offer_to_likers(self, listing=None, listing_title=None):
        """Will send offers to all likers for a given listing"""
        try:
            listing_title = listing.title if listing else listing_title
            lowest_price = listing.lowest_price if listing else self.campaign.lowest_price
            self.logger.info(f'Sending offers to all likers for the following item: {listing_title}')

            self.go_to_closet()

            if self.check_listing(listing_title):
                listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                for listed_item in listed_items:
                    title = listed_item.find_element_by_class_name('tile__title')
                    if title.text == listing_title:
                        listing_price = listed_item.find_element_by_class_name('fw--bold').text[1:]

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
                self.logger.warning(f'The following listing was not found: {listing.title}')
                self.logger.warning(f'Offers not sent to likers')

        except Exception as e:
            self.logger.error(f'{traceback.format_exc()}')
            if not self.check_logged_in():
                self.log_in()

    def check_ip(self, filename=None):
        self.web_driver.get('https://www.whatsmyip.org/')
        host_name = self.locate(By.ID, 'hostname')

        self.logger.debug(f'Hostname: {host_name.text}')
