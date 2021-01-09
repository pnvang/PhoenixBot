from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait as wait
from webdriver_manager.chrome import ChromeDriverManager
from chromedriver_py import binary_path as driver_path
from utils import random_delay, send_webhook, create_msg
from utils.selenium_utils import change_driver
import settings, time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class GameStop:
    def __init__(self, task_id, status_signal, image_signal, product, profile, proxy, monitor_delay, error_delay, max_price):
        self.task_id, self.status_signal, self.image_signal, self.product, self.profile, self.monitor_delay, self.error_delay, self.max_price = task_id, status_signal, image_signal, product, profile, float(
            monitor_delay), float(error_delay), max_price

        starting_msg = "Starting GameStop"
        self.browser = self.init_driver()
        self.product_image = None

        self.SHORT_TIMEOUT = 5
        self.LONG_TIMEOUT = 20

        if settings.dont_buy:
            starting_msg = "Starting GameStop in dev mode; will not actually checkout."

        self.status_signal.emit(create_msg(starting_msg, "normal"))
        
        self.MONITOR_ONLY = settings.notify_only_checkbox
        
        if self.MONITOR_ONLY:
            self.monitor()
        else:
            self.login()
            self.monitor()
            self.add_to_cart()
            self.submit_billing()
            self.submit_order()




    def init_driver(self):
        driver_manager = ChromeDriverManager()
        driver_manager.install()
        # change_driver(self.status_signal, driver_path)
        var = driver_path
        browser = webdriver.Chrome(driver_path)

        browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                  Object.defineProperty(navigator, 'webdriver', {
                   get: () => undefined
                  })
                """
        })

        return browser


    def login(self):
        self.status_signal.emit(create_msg("Logging In..", "normal"))

        self.browser.get("https://www.gamestop.com")

        wait(self.browser, self.LONG_TIMEOUT).until(EC.element_to_be_clickable((By.LINK_TEXT, "MY ACCOUNT")))
        self.browser.find_element_by_link_text('MY ACCOUNT').click()

        wait(self.browser, self.LONG_TIMEOUT).until(EC.element_to_be_clickable((By.ID, "signIn"))).click()

        wait(self.browser, self.LONG_TIMEOUT).until(EC.element_to_be_clickable((By.ID, "login-form-email")))

        email = self.browser.find_element_by_id("login-form-email")
        email.send_keys(settings.gamestop_user)

        wait(self.browser, self.LONG_TIMEOUT).until(EC.element_to_be_clickable((By.ID, "login-form-password")))

        password = self.browser.find_element_by_id("login-form-password")
        password.send_keys(settings.gamestop_pass)

        time.sleep(1) # slight delay for in-between filling out login info and clicking Sign In

        wait(self.browser, self.LONG_TIMEOUT).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="signinCheck"]/button')))
        sign_in_btn = self.browser.find_element_by_xpath('//*[@id="signinCheck"]/button')
        sign_in_btn.click()


    def monitor(self):
        if not self.MONITOR_ONLY:
            logged_in = False
            while not logged_in:
                try: 
                    wait(self.browser, self.LONG_TIMEOUT).until(lambda _: self.browser.current_url == "https://www.gamestop.com/account/")
                    self.status_signal.emit(create_msg("Successfully Logged In", "normal"))
                    logged_in = True
                except:
                    self.status_signal.emit(create_msg("Log in failed. Retrying.", "normal"))
                    self.login()
                
        
        self.status_signal.emit(create_msg("Checking Stock..", "normal"))

        self.browser.get(self.product)
        wait(self.browser, self.LONG_TIMEOUT).until(lambda _: self.browser.current_url == self.product)

        in_stock = False

        while not in_stock:
            try: 
                wait(self.browser, random_delay(self.monitor_delay, settings.random_delay_start, settings.random_delay_stop)).until(EC.element_to_be_clickable((By.XPATH, '//button[@data-buttontext="Add to Cart"]')))
                add_to_cart_btn = self.browser.find_element_by_xpath('//button[@data-buttontext="Add to Cart"]')
                home_delivery_option = self.browser.find_element_by_xpath('//input[@value="home"]')
                add_to_cart_btn.click()
                time.sleep(1)
                if not home_delivery_option.is_enabled() & add_to_cart_btn.is_enabled():
                    self.status_signal.emit(create_msg("Waiting For Restock", "normal"))
                    time.sleep(self.monitor_delay)
                    self.browser.refresh()
                    continue
                in_stock = True
                if not self.MONITOR_ONLY:
                    self.status_signal.emit(create_msg("Added to cart", "normal"))
                    self.browser.get("https://www.gamestop.com/cart/")
                else:
                    self.status_signal.emit(create_msg("Item in stock. Sending notification", "normal"))
                    self.notify()
            except:
                self.status_signal.emit(create_msg("Waiting For Restock", "normal"))
                self.browser.refresh()
                
                
    def notify(self):
        email = settings.gmail_account_email # the email where you sent the email
        password = settings.gmail_account_password
        send_to_email = settings.notification_email # for whom
        subject = 'GameStop'
        message = self.product + " %s"

        msg = MIMEMultipart()
        msg["From"] = email
        msg["To"] = send_to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(message, 'plain'))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(email, password)
        text = msg.as_string()
        
        try:
            server.sendmail(email, send_to_email, text)
            server.quit()
            self.status_signal.emit(create_msg("Notification sent!", "normal"))
        except:
            self.status_signal.emit(create_msg("Notification fail to send!", "normal"))


    def add_to_cart(self):
        wait(self.browser, self.LONG_TIMEOUT).until(lambda _: self.browser.current_url == "https://www.gamestop.com/cart/")
        
        self.status_signal.emit(create_msg("Checking Age Verification", "normal"))

        try:
            seventeen_or_older_btn = self.browser.find_element_by_xpath('//*[@id="age-gate-modal"]/div/div/div[2]/div/div[2]/button')
            seventeen_or_older_btn.click()
            time.sleep(2) # short delay for age verification modal to disappear
            self.browser.get("https://www.gamestop.com/checkout/?stage=payment#payment")
        except:
            self.browser.get("https://www.gamestop.com/checkout/?stage=payment#payment")
        

    def submit_billing(self):
        wait(self.browser, self.LONG_TIMEOUT).until(lambda _: self.browser.current_url == "https://www.gamestop.com/checkout/?stage=payment#payment")

        self.status_signal.emit(create_msg("Entering CVV #", "normal"))

        wait(self.browser, self.LONG_TIMEOUT).until(EC.element_to_be_clickable((By.ID, "saved-payment-security-code")))
        cvv_input = self.browser.find_element_by_id("saved-payment-security-code")
        cvv_input.send_keys(self.profile["card_cvv"])
        order_review_btn = self.browser.find_element_by_class_name("btn.btn-primary.btn-block.submit-payment")
        order_review_btn.click()


    def submit_order(self):
        wait(self.browser, self.LONG_TIMEOUT).until(lambda _: self.browser.current_url == "https://www.gamestop.com/checkout/?stage=placeOrder#placeOrder")

        self.status_signal.emit(create_msg("Submitting Order..", "normal"))

        wait(self.browser, self.LONG_TIMEOUT).until(EC.element_to_be_clickable((By.CLASS_NAME, 'btn.btn-primary.btn-block.place-order')))

        if not settings.dont_buy:
            order_review_btn = self.browser.find_element_by_class_name("btn.btn-primary.btn-block.place-order")
            order_review_btn.click()
            self.status_signal.emit(create_msg("Order Placed", "success"))
            send_webhook("OP", "GameStop", self.profile["profile_name"], self.task_id, self.product_image)
        else:
            self.status_signal.emit(create_msg("Mock Order Placed", "success"))
            send_webhook("OP", "GameStop", self.profile["profile_name"], self.task_id, self.product_image)
