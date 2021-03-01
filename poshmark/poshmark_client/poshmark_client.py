import os
import random
import re
import requests
import time
import traceback

from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, InvalidArgumentException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
    def __init__(self, posh_user, logger):
        self.posh_user = posh_user
        self.logger = logger
        self.web_driver = None
        self.web_driver_options = Options()
        self.web_driver_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.web_driver_options.add_experimental_option('useAutomationExtension', False)
        self.web_driver_options.add_argument('--disable-extensions')
        self.web_driver_options.add_argument('--headless')
        self.web_driver_options.add_argument('--no-sandbox')

    def __enter__(self):
        self.open()

        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def open(self):
        self.web_driver = webdriver.Chrome('/poshmark/poshmark_client/chromedriver', options=self.web_driver_options)
        self.web_driver.implicitly_wait(10)
        if '--headless' in self.web_driver_options.arguments:
            self.web_driver.set_window_size(1920, 1080)

    def close(self):
        self.web_driver.quit()

    def locate(self, by, locator, location_type=None):
        wait = WebDriverWait(self.web_driver, 10)
        if location_type:
            if location_type == 'visibility':
                return wait.until(EC.visibility_of_element_located((by, locator)))
            else:
                return None
        else:
            return wait.until(EC.presence_of_element_located((by, locator)))

    def is_present(self, by, locator):
        try:
            self.web_driver.find_element(by=by, value=locator)
        except NoSuchElementException:
            return False
        return True

    def sleep(self, lower, upper=None):
        seconds = random.randint(lower, upper) if upper else lower
        word = 'second' if seconds == 1 else 'seconds'

        self.logger.info(f'Sleeping for {seconds} {word}')
        time.sleep(seconds)

    def check_for_errors(self, step=None):
        self.logger.info('Checking for errors')
        captcha_errors = [
            'Invalid captcha',
            'Please enter your login information and complete the captcha to continue.'
        ]

        base_error = self.is_present(By.CLASS_NAME, 'base_error_message')
        banner_error = self.is_present(By.CLASS_NAME, 'error_banner')

        if base_error:
            error = self.locate(By.CLASS_NAME, 'base_error_message')
        elif banner_error:
            error = self.locate(By.CLASS_NAME, 'error_banner')
        else:
            self.logger.info('No known errors were encountered')
            return None

        if self.is_present(By.CLASS_NAME, 'base_error_message') or self.is_present(By.CLASS_NAME, 'error_banner'):
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
                    if step == 'registration':
                        self.web_driver.execute_script(f'grecaptcha.getResponse = () => "{captcha_response}"')
                        self.web_driver.execute_script('validateLoginCaptcha()')
                    else:
                        self.web_driver.execute_script(
                            f'document.getElementById("g-recaptcha-response").innerHTML="{captcha_response}";')

                return 'CAPTCHA'

    def register(self):
        if self.posh_user.is_registered:
            pass
        else:
            previous_status = self.posh_user.status
            try:
                self.logger.info(f'Registering {self.posh_user.username}')
                self.posh_user.status = '5'
                self.posh_user.save()
                # Start at home page so it is more realistic
                self.web_driver.get('https://poshmark.com')
                self.logger.info(f'At poshmark homepage - {self.web_driver.current_url}')
                self.logger.info('Locating sign up button')

                # Random wait for more realism
                self.sleep(1, 5)

                # Pick one of the two signup buttons for more randomness and click it
                sign_up_button_xpath = random.choice(['//*[@id="content"]/div/div[1]/div/div[2]/div/div/a',
                                                      '//*[@id="app"]/header/nav/div/div/a[2]'])
                signup_button = self.locate(By.XPATH, sign_up_button_xpath)
                signup_button.click()
                self.logger.info(f'Clicked sign up button - Current URL: {self.web_driver.current_url}')
                self.sleep(1, 4)

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
                self.sleep(1, 2)
                last_name_field.send_keys(self.posh_user.last_name)
                self.sleep(1, 2)
                email_field.send_keys(self.posh_user.email)
                self.sleep(2, 5)
                username_field.send_keys(self.posh_user.username)
                self.sleep(1, 5)
                password_field.send_keys(self.posh_user.password)
                self.sleep(1, 2)
                gender_field.click()
                self.sleep(1)
                gender_options = self.web_driver.find_elements_by_class_name('dropdown__link')
                done_button = self.locate(By.XPATH, '//button[@type="submit"]')

                gender = self.posh_user.get_gender()
                for element in gender_options:
                    if element.text == gender:
                        element.click()

                self.sleep(1, 3)

                # Submit the form
                done_button.click()

                self.logger.info('Form submitted')

                error_code = self.check_for_errors('registration')
                if error_code == 'CAPTCHA':
                    done_button = self.locate(By.XPATH, '//button[@type="submit"]')
                    done_button.click()
                    self.logger.info('Resubmitted form after entering captcha')

                # Sleep for realism
                self.sleep(1, 2)

                # Check if Posh User is now registered
                response = requests.get(f'https://poshmark.com/closet/{self.posh_user.username}')
                user_image_located = self.locate(By.CLASS_NAME, 'user-image')

                if user_image_located and response.status_code == requests.codes.ok:
                    self.posh_user.is_registered = True
                    self.posh_user.status = '1'
                    self.posh_user.save()
                    self.logger.info(f'Successfully registered {self.posh_user.username}, status changed to "Active"')

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
                    self.posh_user.status = '4'
                    self.posh_user.save()
                    if not user_image_located:
                        self.logger.error(f'Registration for {self.posh_user.username} unsuccessful (form not '
                                          f'submitted)')
                    elif response.status_code != requests.codes.ok:
                        self.logger.error(f'Registration for {self.posh_user.username} unsuccessful (could not find '
                                          f'user closet at {response.url})')
                    self.logger.error('Status changed to "Waiting to be registered"')
            except Exception as e:
                self.logger.error(f'Error encountered - Changing status back to {previous_status}')
                self.logger.error(f'{traceback.format_exc()}')

                self.posh_user.status = previous_status
                self.posh_user.save()

    def log_in(self):
        """Will go to the Posh Mark home page and log in using waits for realism"""
        self.logger.info(f'Logging {self.posh_user.username} in')
        if not self.web_driver.current_url == 'https://poshmark.com/':
            self.web_driver.get('https://poshmark.com/')
            self.sleep(1, 3)
        self.logger.info(f'At poshmark homepage - {self.web_driver.current_url}')
        self.logger.info(f'locating login button')
        log_in_nav = self.locate(By.XPATH, '//a[@href="/login"]')
        log_in_nav.click()
        self.logger.info(f'Clicked login button - Current URL: {self.web_driver.current_url}')

        self.sleep(1, 3)
        username_field = self.locate(By.ID, 'login_form_username_email')
        password_field = self.locate(By.ID, 'login_form_password')

        self.logger.info('Filling in form')

        username_field.send_keys(self.posh_user.username)
        self.sleep(1, 2)
        password_field.send_keys(self.posh_user.password)
        password_field.send_keys(Keys.RETURN)
        self.logger.info('Form submitted')

        error_code = self.check_for_errors()

        if error_code == 'CAPTCHA':
            password_field = self.locate(By.ID, 'login_form_password')
            self.sleep(1)
            password_field.send_keys(self.posh_user.password)
            password_field.send_keys(Keys.RETURN)
            self.logger.info('Form resubmitted')

    def check_logged_in(self):
        """Will go to poshmark.com to see if the PoshUser is logged in or not, the bot knows if they are logged in if it
        can find the search bar which is only displayed in the feed page when someone is logged in"""
        self.logger.info('Checking if user is signed in')
        self.web_driver.get('https://poshmark.com')
        result = self.is_present(By.ID, 'searchInput')
        if result:
            self.logger.info('User is logged in')
        else:
            self.logger.info('User is not logged in')

        return result

    def update_profile(self):
        previous_status = self.posh_user.status
        try:
            self.logger.info('Updating Profile')
            self.posh_user.status = '6'
            self.posh_user.save()

            if not self.check_logged_in():
                self.log_in()

            self.sleep(1, 3)

            profile_dropdown = self.locate(By.XPATH, '//*[@id="app"]/header/nav[1]/div/ul/li[5]/div/div[1]/div')
            profile_dropdown.click()

            self.logger.info('Clicked profile dropdown')

            self.sleep(1)

            my_closet_button = self.locate(By.XPATH, f'//a[@href="/closet/{self.posh_user.username}"]')
            my_closet_button.click()

            self.logger.info('Clicked my closet button')

            self.sleep(1, 3)

            edit_profile_button = self.locate(By.XPATH, '//a[@href="/user/edit-profile"]')
            edit_profile_button.click()

            self.logger.info('Clicked on edit profile button')

            self.sleep(1, 3)

            # This while is to ensure that the profile picture path exists and tries 5 times
            attempts = 1
            profile_picture_path = self.posh_user.profile_picture.path
            profile_picture_exists = Path(profile_picture_path).is_file()
            while not profile_picture_exists and attempts < 6:
                self.logger.info(str(profile_picture_path))
                self.logger.warning(f'Could not find profile picture file. Attempt # {attempts}')
                self.sleep(5)
                profile_picture_exists = Path(profile_picture_path).is_file()
                attempts += 1
            else:
                if not profile_picture_exists:
                    self.logger.error('Could not upload profile picture - Picture not found.')
                else:
                    profile_picture = self.locate(By.XPATH, '//*[@id="content"]/div/div[2]/div/div[1]/div[3]/label/input')
                    profile_picture.send_keys(profile_picture_path)

                    apply_button = self.locate(
                        By.XPATH, '//*[@id="content"]/div/div[2]/div/div[1]/div[3]/div/div[2]/div[2]/div/button[2]')
                    apply_button.click()

                    self.logger.info('Profile picture uploaded')

                    self.sleep(1)

            attempts = 1
            header_picture_path = self.posh_user.profile_picture.path
            header_picture_exists = Path(header_picture_path).is_file()
            while not header_picture_exists and attempts < 6:
                self.logger.info(str(header_picture_path))
                self.logger.warning(f'Could not find header picture file. Attempt # {attempts}')
                self.sleep(5)
                header_picture_exists = Path(header_picture_path).is_file()
                attempts += 1
            else:
                if not header_picture_exists:
                    self.logger.error('Could not upload header picture - Picture not found')
                else:
                    header_picture = self.locate(By.XPATH, '//*[@id="content"]/div/div[2]/div/div[1]/div[2]/label/input')
                    header_picture.send_keys(header_picture_path)

                    apply_button = self.locate(
                        By.XPATH, '//*[@id="content"]/div/div[2]/div/div[1]/div[2]/div/div[2]/div[2]/div/button[2]')
                    apply_button.click()

                    self.logger.info('Header picture uploaded')

                    self.sleep(1)

            save_button = self.locate(By.CLASS_NAME, 'btn--primary')
            save_button.click()

            self.logger.info('Profile saved')

            self.posh_user.status = '1'
            self.posh_user.save()

            self.logger.info('Posh User status changed to "Active"')
        except Exception as e:
            self.logger.error(f'Error encountered - Changing status back to {previous_status}')
            self.logger.error(f'{traceback.format_exc()}')

            self.posh_user.status = previous_status
            self.posh_user.save()

    def check_news(self):
        """If the PoshUser is logged in it will check their new else it will log them in then check their news"""
        if not self.check_logged_in():
            self.log_in()
        else:
            badge = self.locate(By.CLASS_NAME, 'badge badge--red badge--right')
            if badge:
                news_nav = self.locate(By.XPATH, '//a[@href="/news"]')
                news_nav.click()

    def check_offers(self):
        self.logger.info('Checking news')
        if not self.check_logged_in():
            self.log_in()
        else:
            offers_nav = self.locate(By.XPATH, '//a[@href="/offers/my_offers"]')
            offers_nav.click()