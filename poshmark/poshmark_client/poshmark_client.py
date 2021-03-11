import os
import random
import re
import requests
import time
import traceback

from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
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
        wait = WebDriverWait(self.web_driver, 10)
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
        wait = WebDriverWait(self.web_driver, 10)
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

    def check_for_errors(self, step=None):
        """This will check for errors on the current page and handle them as necessary"""
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

    def check_listing(self, listing_title):
        """Will check if a listing exists on the user's closet. Without this listing it is"""
        previous_status = self.posh_user.status
        try:
            self.logger.info(f'Checking for "{listing_title}" listing')

            self.go_to_closet()

            if self.is_present(By.CLASS_NAME, 'tile__title'):
                titles = self.locate_all(By.CLASS_NAME, 'tile__title')
                for title in titles:
                    if listing_title in title.text:
                        self.posh_user.meet_posh = True
                        self.posh_user.save()
                        self.logger.info(f'"{listing_title}" listing found')
                        return True

            self.logger.warning(f'"{listing_title}" listing not found')

            return False

        except Exception as e:
            self.logger.error(f'Error encountered - Changing status back to {previous_status}')
            self.logger.error(f'{traceback.format_exc()}')

            self.posh_user.status = previous_status
            self.posh_user.save()

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

    def register(self):
        """Will register a given user to poshmark"""
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
                self.sleep(5)

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

    def go_to_closet(self):
        """Ensures the current url for the web driver is at users poshmark closet"""
        previous_status = self.posh_user.status
        try:
            if self.web_driver.current_url != f'https://poshmark.com/closet/{self.posh_user.username}':
                self.logger.info(f"Going to {self.posh_user.username}'s closet")

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
            else:
                self.logger.info(f"Already at {self.posh_user.username}'s closet, refreshing.")
                self.web_driver.refresh()

        except Exception as e:
            self.logger.error(f'Error encountered - Changing status back to {previous_status}')
            self.logger.error(f'{traceback.format_exc()}')

            self.posh_user.status = previous_status
            self.posh_user.save()

    def update_profile(self):
        """Updates a user profile with their profile picture and header picture"""
        previous_status = self.posh_user.status
        try:
            self.logger.info('Updating Profile')
            self.posh_user.status = '6'
            self.posh_user.save()

            self.go_to_closet()

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

    def list_item(self, listing):
        """Will list an item on poshmark for the user"""
        previous_status = self.posh_user.status
        try:
            self.logger.info(f'Listing the following item: {listing.title}')

            if not self.check_logged_in():
                self.log_in()

            self.sleep(1, 3)

            sell_button = self.locate(By.XPATH, '//*[@id="app"]/header/nav[2]/div[1]/ul[2]/li[2]/a')
            sell_button.click()

            self.logger.info('Clicked "SELL ON POSHMARK" button')

            self.sleep(1, 2)

            # Set category and sub category
            self.logger.info('Setting category')
            category_dropdown = self.locate(
                By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/section[3]/div/div[2]/div[1]/div'
            )
            category_dropdown.click()

            self.sleep(2)

            space_index = listing.category.find(' ')
            primary_category = listing.category[:space_index]
            secondary_category = listing.category[space_index + 1:]
            primary_categories = self.locate_all(By.CLASS_NAME, 'p--l--7')
            for category in primary_categories:
                if category.text == primary_category:
                    category.click()
                    break

            self.sleep(1, 3)

            secondary_categories = self.locate_all(By.CLASS_NAME, 'p--l--7')
            for category in secondary_categories[1:]:
                if category.text == secondary_category:
                    category.click()
                    break

            self.logger.info('Category set')

            self.sleep(1)

            self.logger.info('Setting subcategory')

            subcategory_menu = self.locate(By.CLASS_NAME, 'dropdown__menu--expanded')
            subcategories = subcategory_menu.find_elements_by_tag_name('a')

            for subcategory in subcategories:
                if subcategory.text == listing.subcategory:
                    subcategory.click()
                    break

            self.logger.info('Subcategory set')

            self.sleep(2)

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
            custom_size_input.send_keys(listing.size)
            save_button.click()
            done_button.click()

            self.logger.info('Size set')

            self.sleep(1, 2)

            # Upload listing photos, you have to upload the first picture then click apply before moving on to upload
            # the rest, otherwise errors come up.
            self.logger.info('Uploading photos')
            listing_photos = listing.get_photos()
            upload_photos_field = self.locate(By.ID, 'img-file-input')
            upload_photos_field.send_keys(listing_photos[0])

            apply_button = self.locate(By.XPATH, '//*[@id="imagePlaceholder"]/div[2]/div[2]/div[2]/div/button[2]')
            apply_button.click()

            self.sleep(1)

            upload_photos_field = self.locate(By.ID, 'img-file-input')
            if len(listing_photos) > 1:
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

            original_price_field = self.locate(
                By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/section[8]/div/div/div[2]/input'
            )
            listing_price_field = self.locate(
                By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/section[8]/div/div/div[2]/div[1]/input'
            )

            # Send all the information to their respected fields
            title_field.send_keys(listing.title)
            self.sleep(1, 2)

            for part in listing.description.split('\n'):
                description_field.send_keys(part)
                ActionChains(self.web_driver).key_down(Keys.SHIFT).key_down(Keys.ENTER).key_up(Keys.SHIFT).key_up(
                    Keys.ENTER).perform()

            self.sleep(1, 2)
            original_price_field.send_keys(str(listing.original_price))
            self.sleep(1, 2)
            listing_price_field.send_keys(str(listing.listing_price))
            self.sleep(1, 2)

            if listing.tags:
                tags_button = self.locate(
                    By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/section[5]/div/div[2]/div[1]/button[1]', 'clickable'
                )
                self.web_driver.execute_script("arguments[0].click();", tags_button)

            self.sleep(1, 3)

            next_button = self.locate(By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/div[2]/button')
            next_button.click()

            list_item_button = self.locate(
                By.XPATH, '//*[@id="content"]/div/div[1]/div[2]/div[3]/div[2]/div[2]/div[2]/button'
            )
            list_item_button.click()

            self.logger.info('Item listed successfully with no brand')

            while listing.status != 2:
                if self.update_listing_brand(listing):
                    self.sleep(1, 3)
                else:
                    break

            self.sleep(2, 3)

        except Exception as e:
            self.logger.error(f'Error encountered - Changing status back to {previous_status}')
            self.logger.error(f'{traceback.format_exc()}')

            self.posh_user.status = previous_status
            self.posh_user.save()

    def update_listing_brand(self, listing):
        """Will update the brand on a listing"""
        previous_status = self.posh_user.status
        try:
            self.logger.info(f'Updating the brand on following item: {listing.title}')

            self.go_to_closet()

            if self.check_listing(listing.title):
                listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                for listed_item in listed_items:
                    title = listed_item.find_element_by_class_name('tile__title')
                    if title.text == listing.title:
                        listing_button = listed_item.find_element_by_class_name('tile__covershot')
                        listing_button.click()

                        self.sleep(1, 2)

                        edit_listing_button = self.locate(By.XPATH, '//*[@id="content"]/div/div/div[3]/div[2]/div[1]/a')
                        edit_listing_button.click()

                        brand_field = self.locate(
                            By.XPATH,
                            '//*[@id="content"]/div/div[1]/div/section[6]/div/div[2]/div[1]/div[1]/div/input'
                        )
                        brand_field.clear()
                        if listing.status == 1:
                            brand_field.send_keys('Saks Fifth Avenue')
                            listing.status += 1
                            listing.save()
                            self.sleep(1, 2)
                        elif listing.status == 2:
                            brand_field.send_keys(listing.brand)
                            listing.status += 1
                            listing.save()
                            self.sleep(1, 2)
            else:
                self.logger.error('Could not update listing - It does not exist')
                return False

        except Exception as e:
            self.logger.error(f'Error encountered - Changing status back to {previous_status}')
            self.logger.error(f'{traceback.format_exc()}')

            self.posh_user.status = previous_status
            self.posh_user.save()

    def share_item(self, listing):
        """Will share an item in the closet"""
        previous_status = self.posh_user.status
        try:
            self.logger.info(f'Sharing the following item: {listing.title}')

            self.logger.info(self.posh_user)

            if self.posh_user.meet_posh:
                self.go_to_closet()
                some_listing_present = self.is_present(By.CLASS_NAME, 'card--small')
                if some_listing_present and not self.posh_user.error_during_listing:
                    if self.check_listing(listing.title):
                        listed_items = self.locate_all(By.CLASS_NAME, 'card--small')
                        for listed_item in listed_items:
                            title = listed_item.find_element_by_class_name('tile__title')
                            if title.text == listing.title:
                                share_button = listed_item.find_element_by_class_name('social-action-bar__share')
                                share_button.click()
                                self.sleep(1)
                                to_followers_button = self.locate(By.CLASS_NAME, 'internal-share__link')
                                to_followers_button.click()
                    else:
                        self.list_item(listing)
                elif not some_listing_present and self.posh_user.error_during_listing:
                    self.logger.critical('Could not list item. User seems to be inactive.')
                    self.logger.info('Setting status of user to "Inactive"')
                    self.posh_user.status = '2'
                    self.posh_user.save()
                else:
                    self.logger.warning('No listings for this user. User Inactive? - Listing item to test')
                    self.list_item(listing)
                    self.posh_user.error_during_listing = True
                    self.posh_user.save()

            else:
                self.logger.warning('"Meet your Posher" listing still has not been posted. Checking now...')
                self.check_listing('Meet your Posher')

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
