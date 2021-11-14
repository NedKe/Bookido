from datetime import datetime, timedelta
import uuid
import gspread
from google.oauth2.service_account import Credentials
from pydantic import BaseModel
from gcalendar import add_event, update_event_description

SCOPES_SHEETS = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive'
    ]

CREDS = Credentials.from_service_account_file('creds.json')
SCOPED_CREDS = CREDS.with_scopes(SCOPES_SHEETS)
GSPREAD_CLIENT = gspread.authorize(SCOPED_CREDS)
SHEET = GSPREAD_CLIENT.open('fartoor_products')
products_sheet = SHEET.worksheet('products')

GMT_OFF = '+01:00'


class Product(BaseModel):
    """Product model holding information about a prouduct in the application"""
    id: str
    calendar_id: str
    title: str
    description: str
    address: str
    capacity: str
    price: str
    date: str
    time: str
    emails: str


class ProductRow(BaseModel):
    """Product row model storing row_num to access product row in the sheet"""
    row_num: int
    product: Product


class ProductNotFoundException(Exception):
    """
    Exception to be thrown when a product not found in the list of products
    """
    pass


class CapacityReachedException(Exception):
    """
    Exception to be thrown when capacity is reached while booking a product
    """
    pass


def add_booking(product_id, email):
    """
    Creates a booking for a product by adding customer's email to the datastore
    and creating an Google calendar event based on product timing

    :param product_id: product to be booked
    :param email: customer's email
    """
    product_row = get_product_row(product_id)
    product = product_row.product
    emails = product.emails.split(',') if product.emails != '' else []
    if len(emails) > int(product.capacity) - 1:
        raise CapacityReachedException("capacity reached")
    emails.append(email)

    emails_to_store = email if len(emails) == 1 else ','.join(emails)
    products_sheet.update_cell(product_row.row_num, 10, emails_to_store)
    description = build_description(product.description, product.capacity, len(emails))
    description += '\n' + '\n'.join(emails_to_store.split(','))
    update_event_description(product.calendar_id, description)


def get_product_row(product_id):
    """
    Returns the product found in the list of products using product_id
    :param product_id
    """
    for product_row in list_products():
        if product_row.product.id == product_id:
            return product_row
    raise ProductNotFoundException("product not found")


def build_description(product_description, product_capacity, num_booked):
    """
    Builds the description for the summary section of Google calendar event
    :param product_description: description of a product
    :param product_capacity: capacity of the product
    :param num_booked: the number of booked customers to be shown in calendar
    """
    return f'{product_description} ({num_booked}/{product_capacity})'


def add_product(product):
    """
    Persists a product in Google sheet and creates an event in Goole calendar
    :param product:  Product that is added by admins
    """
    product_values = list(product.dict().values())
    products_sheet.append_row(product_values)
    event = {
        'id': product.calendar_id,
        'summary': product.title,
        'location': product.address,
        'description': build_description(product.description, product.capacity, 0),
        'start': {
            'dateTime': convert_to_gcalendar_friendly_date(product.date,product.time),
            'timeZone': 'America/Los_Angeles',
        },
        'end': {
            'dateTime': convert_to_gcalendar_friendly_date(product.date, (datetime.strptime(product.time, '%H:%M:%S') + timedelta(minutes=45)).strftime('%H:%M:%S')),
            'timeZone': 'America/Los_Angeles',
        }
    }
    add_event(event)


def convert_to_gcalendar_friendly_date(date, time):
    """
    Converts date and time parameters to Google calendar friendly format
    :param date: date of an event
    :param time: time of an event
    """
    return f'{date}T{time}{GMT_OFF}'


def generate_new_product_id():
    """
    Generates a unique id for a product based on the already saved
    records in the Google spreadsheet
    """
    return str(len(products_sheet.get_all_records()))


def generate_calendar_id():
    """Generates Calendar id to for Google calendar events"""
    return str(uuid.uuid4()).replace('-', '')


def list_products():
    products = products_sheet.get_all_records()
    return [ProductRow(row_num=i+2, product=Product(id=p['id'], calendar_id=p['calendar_id'], title=p['title'], description=p['description'], address=p['address'], capacity=p['capacity'], price=p['price'], date=p['date'], time=p['time'], emails=p['emails'])) for i, p in enumerate(products)]


def add_product_raw(title, description, address, price, capacity, date, time):
    """
    Creates a new product model and stores it using add_product method
    :param title
    :param description
    :param address
    :param price
    :param capacity
    :param date
    :param time
    """
    calendar_id = generate_calendar_id()
    product_id = generate_new_product_id()
    new_product = Product(id=product_id, calendar_id=calendar_id, title=title, description=description, address=address, price=price, capacity=capacity, date=date, time=time, emails='')
    add_product(sample_product)
