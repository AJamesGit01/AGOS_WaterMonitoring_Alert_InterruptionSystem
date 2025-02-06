import flet as ft
import time
import mysql.connector
import serial
import threading
import bcrypt

# Set up serial communication with Arduino
ser = serial.Serial('COM9', 9600)  # Adjust COM port as needed

#database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="agos_system"
)

cursor = db.cursor()

def ensure_db_connection():
    """
    Ensure the database connection is active.
    """
    global db
    if not db.is_connected():
        try:
            db.reconnect(attempts=3, delay=5)
            print("Reconnected to the database.")
        except mysql.connector.Error as e:
            print(f"Error reconnecting to the database: {e}")


def get_water_level_from_db():
    cursor.execute("SELECT percentage FROM tbl_water_data ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    return result[0] if result else 0


def get_water_interruptions_from_db():
    try:
        # Ensure the cursor is valid and database connection is active
        if not db.is_connected():
            db.reconnect(attempts=3, delay=5)  # Reconnect if needed
            print("Reconnected to the database.")

        # Execute the query to fetch water interruption data
        cursor.execute("SELECT location, time_date, details FROM tbl_water_interruptions")
        result = cursor.fetchall()  # Fetch all rows at once

        if result:
            # Return the formatted result as a list of dictionaries
            return [{"location": row[0], "time_date": row[1], "details": row[2]} for row in result]
        else:
            print("No data found in tbl_water_interruptions.")
            return []  # Return an empty list if no results found

    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        return []  # Return an empty list in case of error


# Function to create the donut chart
def create_donut_chart(level):
    # Determine color based on the water level percentage
    if level > 70:
        color = "green"  # Safe level
    elif level > 30:
        color = "yellow"  # Warning level
    else:
        color = "red"  # Critical level

    return ft.Stack(
        [
            ft.ProgressRing(
                value=level / 100,
                stroke_width=10,
                color=color,  # Set the color dynamically
                width=150,
                height=150,
            ),
            ft.Container(
                width=90,
                height=90,
                bgcolor=color,  # Set the background color dynamically
                border_radius=45,
                alignment=ft.alignment.center,
            ),
            ft.Container(
                content=ft.Text(
                    f"{level}%",
                    size=24,
                    weight="bold",
                    color="white",
                ),
                alignment=ft.alignment.center,
            ),
        ],
        alignment=ft.alignment.center,
    )


# Function to update the chart with the latest water level
def update_chart():
    level = get_water_level_from_db()  # Get the water level from the database
    return create_donut_chart(level)


def store_notification(title, content):
    try:
        cursor.execute("""
            INSERT INTO notifications (title, content, unread)
            VALUES (%s, %s, 1) -- 1 means unread
        """, (title, content))
        db.commit()
        print(f"Notification stored: {title} - {content}")
    except mysql.connector.Error as e:
        print(f"Error storing notification: {e}")

def send_notification(page, title, message):
    page.send_notification(
        title=title,
        body=message,
    )


def check_and_notify(page, percentage):
    if percentage <= 20:
        title = "Emergency Alert"
        message = "Water level is at a critical level (20%). Immediate action required!"
        store_notification(title, message)
        send_notification(page, title, message)
    elif percentage <= 40:
        title = "Preparation Alert"
        message = "Water level is low (40%). Prepare accordingly."
        store_notification(title, message)
        send_notification(page, title, message)
    elif percentage >= 70:
        title = "Warning Alert"
        message = "Water level is high (70%). Stay vigilant."
        store_notification(title, message)
        send_notification(page, title, message)


def store_notification(title, content):
    try:
        cursor.execute("""
            INSERT INTO notifications (title, content, unread)
            VALUES (%s, %s, 1) -- 1 means unread
        """, (title, content))
        db.commit()
        print(f"Notification stored: {title} - {content}")
    except mysql.connector.Error as e:
        print(f"Error storing notification: {e}")

def get_unread_count():
    """
    Get the count of unread notifications from the database.
    """
    try:
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE unread = 1")
        count = cursor.fetchone()[0]
        return count
    except mysql.connector.Error as e:
        print(f"Error fetching unread notifications: {e}")
        return 0

def mark_as_read(notification_id):
    try:
        cursor.execute("""
            UPDATE notifications
            SET unread = 0
            WHERE id = %s
        """, (notification_id,))
        db.commit()
        print(f"Notification {notification_id} marked as read.")
    except mysql.connector.Error as e:
        print(f"Error marking notification as read: {e}")


def read_water_level():
    """
    Continuously read water level data from the Arduino and update the database.
    Also, check for specific percentage thresholds and add notifications if needed.
    """
    while True:
        try:
            if ser.in_waiting > 0:
                # Read data from Arduino (water level and percentage)
                data = ser.readline().decode('utf-8').strip()
                water_level, percentage, range_value = map(int, data.split(","))

                # Insert water level and percentage into the water_data table
                with db.cursor() as cursor:  # Use context manager for the cursor
                    cursor.execute("""
                        INSERT INTO tbl_water_data (level, percentage)
                        VALUES (%s, %s)
                    """, (water_level, percentage))
                    db.commit()  # Commit the transaction to the database

                print(f"Water level: {water_level}, Percentage: {percentage}")

                # Check for specific thresholds and add notifications
                if percentage >= 70:
                    title = "Warning Alert"
                    message = "Water level is high (70%). Stay vigilant."
                    with db.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO notifications (title, content, unread)
                            VALUES (%s, %s, %s)
                        """, (title, message, 1))  # 1 indicates unread
                        db.commit()
                    print(f"Notification added: {title} - {message}")

                elif percentage <= 20:
                    title = "Emergency Alert"
                    message = "Water level is at a critical level (20%). Immediate action required!"
                    with db.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO notifications (title, content, unread)
                            VALUES (%s, %s, %s)
                        """, (title, message, 1))
                        db.commit()
                    print(f"Notification added: {title} - {message}")

                elif percentage <= 40:
                    title = "Preparation Alert"
                    message = "Water level is low (40%). Prepare accordingly."
                    with db.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO notifications (title, content, unread)
                            VALUES (%s, %s, %s)
                        """, (title, message, 1))
                        db.commit()
                    print(f"Notification added: {title} - {message}")

        except Exception as e:
            print(f"Error: {e}")


def main(page: ft.Page):
    page.title = "Agos App"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    # Set dynamic padding for mobile and desktop
    page.padding = 40 if page.window_width and page.window_width > 600 else 20
    page.scroll = "adaptive"

    email_field = ft.TextField(label="Email", hint_text="Enter your email", prefix_icon=ft.icons.PERSON)
    password_field = ft.TextField(label="Password", hint_text="Enter your password", prefix_icon=ft.icons.LOCK,
                                  password=True, can_reveal_password=True)
    reg_username_field = ft.TextField(label="Username", prefix_icon=ft.icons.PERSON)
    reg_email_field = ft.TextField(label="Email", prefix_icon=ft.icons.EMAIL)
    reg_password_field = ft.TextField(label="Password", password=True, can_reveal_password=True,
                                      prefix_icon=ft.icons.LOCK)
    reg_confirm_password_field = ft.TextField(label="Confirm Password", password=True, can_reveal_password=True,
                                              prefix_icon=ft.icons.LOCK)
    last_name_field = ft.TextField(label="Last Name", prefix_icon=ft.icons.PERSON)
    first_name_field = ft.TextField(label="First Name", prefix_icon=ft.icons.PERSON)
    middle_name_field = ft.TextField(label="Middle Name", prefix_icon=ft.icons.PERSON)
    age_field = ft.TextField(label="Age", prefix_icon=ft.icons.CAKE)
    phone_number_field = ft.TextField(label="Contact No.", prefix_icon=ft.icons.PHONE)
    gender_field = ft.Dropdown(
        label="Gender",
        prefix_icon=ft.icons.WC,
        options=[
            ft.dropdown.Option("Male"),
            ft.dropdown.Option("Female"),
            ft.dropdown.Option("Other"),
        ],
    )

    # Address Section
    province_field = ft.TextField(label="Province", prefix_icon=ft.icons.LOCATION_CITY)
    city_field = ft.TextField(label="City", prefix_icon=ft.icons.LOCATION_CITY)
    barangay_field = ft.TextField(label="Barangay", prefix_icon=ft.icons.HOME)
    house_number_field = ft.TextField(label="House No.", prefix_icon=ft.icons.HOUSE)
    street_field = ft.TextField(label="Street", prefix_icon=ft.icons.HOUSE)

    water_level = 50

 

    # Container for the donut chart
    chart_container = ft.Container()

    # Test storing a notification
    store_notification("Test Title", "This is a test notification.")


    # Function to refresh the chart dynamically
    def refresh_chart():
        while True:
            try:
                # Get the latest water level
                water_level = get_water_level_from_db()

                # Update the chart content
                chart_container.content = create_donut_chart(water_level)
                page.update()

                # Wait for 5 seconds before refreshing again
                time.sleep(5)
            except Exception as e:
                print(f"Error refreshing chart: {e}")

    update_chart()

    def sign_in_action(e):
        try:
            cursor.execute(
                "SELECT user_id, account_role, profile_status, password FROM tbl_user_account WHERE (email = %s OR username = %s)",
                (email_field.value, email_field.value)
            )
            result = cursor.fetchone()

            # validation
            if result:
                user_id, account_role, profile_status, stored_password = result

                # Hash the entered password using bcrypt for comparison
                entered_password = password_field.value.encode('utf-8')  # Convert entered password to bytes

                # Compare the entered password with the stored bcrypt password hash
                if bcrypt.checkpw(entered_password, stored_password.encode('utf-8')):  # Compare hashes
                    # Store user_id in the session (client storage)
                    page.client_storage.set("session_user_id", user_id)

                    # If profile status is pending, show profile creation page
                    if profile_status == "pending":
                        show_createprofile(e)
                    else:
                        # Redirect based on account role
                        if account_role == "admin":
                            admin_page()
                        elif account_role == "user":
                            user_page()
                else:
                    # Incorrect password
                    page.snack_bar = ft.SnackBar(ft.Text("Incorrect email or password!"), bgcolor=ft.colors.RED)
                    page.snack_bar.open = True

        except mysql.connector.Error as err:
            page.snack_bar = ft.SnackBar(ft.Text(f"Database error: {err}"), bgcolor=ft.colors.RED)

    def hash_password(password):
        """Hashes the password using bcrypt before saving it into the database."""
        salt = bcrypt.gensalt()  # Generate a salt for bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)  # Hash the password
        return hashed_password

    def signup_action(e):
        username = reg_username_field.value
        email = reg_email_field.value
        password = reg_password_field.value
        conpassword = reg_confirm_password_field.value

        if not username or not email or not password or not conpassword:
            page.snack_bar = ft.SnackBar(ft.Text("Please fill in all fields!"), bgcolor=ft.colors.RED)
            page.snack_bar.open = True
            page.update()
            return

        if password != conpassword:
            page.snack_bar = ft.SnackBar(ft.Text("Passwords do not match!"), bgcolor=ft.colors.RED)
            page.snack_bar.open = True
            page.update()
            return

        try:
            cursor.execute("SELECT COUNT(*) FROM tbl_user_account WHERE email = %s",
                           (email,))
            result = cursor.fetchone()

            if result[0] > 0:
                page.snack_bar = ft.SnackBar(ft.Text("Email is already registered!"), bgcolor=ft.colors.RED)
                page.snack_bar.open = True
                page.update()
                return

            salt = bcrypt.gensalt()
            hashed_password = hash_password(password)

            cursor.execute(
                "INSERT INTO tbl_user_account (username, email, password, account_role, profile_status) VALUES (%s, %s, %s, %s, %s)",
                (username, email, hashed_password, "user", "pending")
            )

            db.commit()
            page.snack_bar = ft.SnackBar(ft.Text("Sign-up successful!"), bgcolor=ft.colors.GREEN)
            page.snack_bar.open = True
            page.update()

            page.controls.clear()  # Clear the current page content
            show_signin(None)  # Show the sign-in page

            page.update()  # Refresh the page to show the updated content

        except mysql.connector.Error as err:
            page.snack_bar = ft.SnackBar(ft.Text(f"Database error: {err}"), bgcolor=ft.colors.RED)
            page.snack_bar.open = True
            page.update()

    def logout_confirmation(e):
        """
        Show confirmation dialog before logging out.
        """

        def confirm_logout(e):
            """
            Perform logout action after confirmation.
            """
            # Clear session data
            page.client_storage.remove("session_user_id")

            # Show confirmation message
            page.snack_bar = ft.SnackBar(
                ft.Text("You have been logged out successfully."),
                bgcolor=ft.colors.GREEN
            )
            page.snack_bar.open = True

            # Redirect to the login page
            show_signin(e)
            page.dialog.open = False  # Replace with your function to navigate to the login page

            # Update the page to reflect changes
            page.update()
            page.dialog.open = False


        def cancel_logout(e):
            """
            Close the confirmation dialog without logging out.
            """
            page.dialog.open = False
            page.update()

        # Create and show the confirmation dialog
        confirmation_dialog = ft.AlertDialog(
            title=ft.Text("Confirm Logout"),
            content=ft.Text("Are you sure you want to log out?"),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_logout),
                ft.TextButton("Logout", on_click=confirm_logout),
            ],
        )

        # Open the dialog
        page.dialog = confirmation_dialog
        page.dialog.open = True
        page.update()

    def create_profile_action(e):
        # Retrieve user_id from session
        user_id = page.client_storage.get("session_user_id")

        if not user_id:
            # If user_id is not in session, show an error
            page.snack_bar = ft.SnackBar(
                ft.Text("Session expired. Please log in again."),
                bgcolor=ft.colors.RED
            )
            page.snack_bar.open = True
            page.update()
            return

        try:
            # Retrieve values from the input fields
            last_name = last_name_field.value
            first_name = first_name_field.value
            middle_name = middle_name_field.value
            age = age_field.value
            phone_number = phone_number_field.value
            gender = gender_field.value
            province = province_field.value
            city = city_field.value
            barangay = barangay_field.value
            house_number = house_number_field.value
            street = street_field.value

            # Validation: Ensure all fields are filled
            if not all(
                    [last_name, first_name, age, phone_number, gender, province, city, barangay, house_number,
                     street]):
                page.snack_bar = ft.SnackBar(
                    ft.Text("Please fill out all fields!"),
                    bgcolor=ft.colors.RED
                )
                page.snack_bar.open = True
                page.update()
                return

            # Insert address data into the tbl_address table
            cursor.execute("""
                INSERT INTO tbl_address (province, city, barangay, house_number, street, user_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (province, city, barangay, house_number, street, user_id))

            # Insert user profile data into the tbl_user_profile table, including the address_id
            cursor.execute("""
                INSERT INTO tbl_profile (
                    user_id, last_name, first_name, middle_name, age, contact_number, gender
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, last_name, first_name, middle_name, age, phone_number, gender
            ))

            # Commit the transaction
            db.commit()

            # Update profile_status in tbl_user_account
            cursor.execute("""
                UPDATE tbl_user_account
                SET profile_status = 'complete'
                WHERE user_id = %s
            """, (user_id,))
            db.commit()

            # Show success message and redirect to the appropriate page
            page.snack_bar = ft.SnackBar(
                ft.Text("Profile created successfully!"),
                bgcolor=ft.colors.GREEN
            )
            page.snack_bar.open = True

            # Redirect to user or admin page based on account role
            cursor.execute("SELECT account_role FROM tbl_user_account WHERE user_id = %s", (user_id,))
            account_role = cursor.fetchone()[0]

            if account_role == "admin":
                admin_page()
            elif account_role == "user":
                user_page()

        except mysql.connector.Error as err:
            # Handle database errors
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Database error: {err}"),
                bgcolor=ft.colors.RED
            )
            page.snack_bar.open = True

        finally:
            page.update()

    def signin_view():
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Image(
                                src="agos_logo.png",
                                width=150,
                                height=150,
                                fit=ft.ImageFit.CONTAIN,
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    email_field,
                    password_field,
                    ft.Row(
                        [
                            ft.TextButton(
                                "Forgot your password?",
                                on_click=lambda e: show_forgotPassword(e),
                                style=ft.ButtonStyle(color=ft.colors.BLUE),
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                text="SIGN IN",
                                on_click=sign_in_action,
                                width=200,
                                style=ft.ButtonStyle(bgcolor=ft.colors.CYAN, color=ft.colors.WHITE),
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    # "Or" Text
                    ft.Row(
                        [
                            ft.Text("or", size=16, weight="bold", color=ft.colors.GREY),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),

                    ft.Row(
                        [
                            ft.Text("Don't have an account?"),
                            ft.TextButton(
                                "REGISTER",
                                on_click=show_signup,
                                style=ft.ButtonStyle(color=ft.colors.BLUE),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
            padding=20,
            alignment=ft.alignment.center,
        )

    def signup_view():
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Image(src="agos_logo.png", width=150, height=150, fit=ft.ImageFit.CONTAIN)
                ], alignment=ft.MainAxisAlignment.CENTER),
                reg_username_field,
                reg_email_field,
                reg_password_field,
                reg_confirm_password_field,
                ft.Row(
                    [
                        ft.ElevatedButton(
                            text="SIGN UP",
                            on_click=signup_action,
                            width=200,
                            style=ft.ButtonStyle(
                                bgcolor=ft.colors.CYAN,
                                color=ft.colors.WHITE,
                            ),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                # "or" separator
                ft.Row(
                    [
                        ft.Text(
                            "or",
                            size=16,
                            weight="bold",
                            color=ft.colors.GREY,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),

                # "Already have an account?" and Sign In link
                ft.Row(
                    [
                        ft.Text("Already have an account?"),
                        ft.TextButton(
                            "LOG IN",
                            on_click=show_signin,
                            style=ft.ButtonStyle(color=ft.colors.BLUE),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
            padding=20,
            alignment=ft.alignment.center,
        )

    def create_profile():
        return ft.Container(
            content=ft.Column(
                [
                    # Logo Row
                    ft.Row(
                        [
                            ft.Image(
                                src="agos_logo.png",
                                width=150,
                                height=150,
                                fit=ft.ImageFit.CONTAIN
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER
                    ),

                    # Personal Information Section
                    ft.Text("Personal Information", weight=ft.FontWeight.BOLD, size=18),
                    last_name_field,
                    first_name_field,
                    middle_name_field,
                    age_field,
                    phone_number_field,
                    gender_field,
                    # Address Section
                    ft.Text("Address", weight=ft.FontWeight.BOLD, size=18),
                    province_field,
                    city_field,
                    barangay_field,
                    house_number_field,
                    street_field,

                    # Sign Up Button
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                text="Save Changes",
                                on_click=create_profile_action,
                                width=200,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.colors.CYAN,
                                    color=ft.colors.WHITE,
                                ),
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20  # Add spacing between elements for better layout
            ),
            padding=20,  # Padding for the container
            alignment=ft.alignment.center,  # Center-align the container
        )

    def forgot_password():
        """
        Forgot Password UI Flow:
        1. Input Email to receive pin.
        2. Confirm Email and receive pin.
        3. Input 6-digit pin and confirm.
        4. Set New Password.
        """

        # Step 1: Enter Email Address
        email_input = ft.TextField(label="Enter your email", keyboard_type=ft.KeyboardType.EMAIL)
        send_pin_button = ft.ElevatedButton("Send Pin", on_click=None)  # Placeholder for sending pin logic
        step1_container = ft.Container(
            content=ft.Column(
                [
                    email_input,
                    ft.Row([send_pin_button], alignment=ft.MainAxisAlignment.CENTER),  # Centered Button
                ],
                spacing=10,
            ),
            padding=20,
        )

        # Step 2: Enter 6-Digit Pin (Visible only after email is confirmed)
        pin_input = ft.TextField(label="Enter 6-digit Pin", keyboard_type=ft.KeyboardType.NUMBER)
        confirm_pin_button = ft.ElevatedButton("Confirm Pin", on_click=None)  # Placeholder for pin confirmation logic
        step2_container = ft.Container(
            content=ft.Column(
                [
                    pin_input,
                    ft.Row([confirm_pin_button], alignment=ft.MainAxisAlignment.CENTER),  # Centered Button
                ],
                spacing=10,
            ),
            padding=20,
            visible=False,  # Initially hidden, will be displayed after email is confirmed
        )

        # Step 3: Set New Password (Visible only after pin confirmation)
        new_password_input = ft.TextField(label="Enter new password", password=True)
        confirm_password_input = ft.TextField(label="Confirm new password", password=True)
        set_new_password_button = ft.ElevatedButton("Set New Password",
                                                    on_click=None)  # Placeholder for password update logic
        step3_container = ft.Container(
            content=ft.Column(
                [
                    new_password_input,
                    confirm_password_input,
                    ft.Row([set_new_password_button], alignment=ft.MainAxisAlignment.CENTER),  # Centered Button
                ],
                spacing=10,
            ),
            padding=20,
            visible=False,  # Initially hidden, will be displayed after pin is confirmed
        )

        def on_send_pin_click(e):
            # Logic to send pin to email
            page.snack_bar = ft.SnackBar(ft.Text("Pin sent to your email!"))
            page.snack_bar.open()

            # Hide email input and show pin input
            step1_container.visible = False
            step2_container.visible = True
            page.update()

        def on_confirm_pin_click(e):
            # Logic to confirm the pin
            page.snack_bar = ft.SnackBar(ft.Text("Pin confirmed!"))
            page.snack_bar.open()

            # Hide pin input and show new password input
            step2_container.visible = False
            step3_container.visible = True
            page.update()

        # Attach actions to buttons
        send_pin_button.on_click = on_send_pin_click
        confirm_pin_button.on_click = on_confirm_pin_click

        return ft.Container(
            content=ft.Column(
                [
                    # Navigation Bar
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.ElevatedButton(
                                    on_click=show_signin,
                                    content=ft.Image(
                                        src="back.png",  # Replace with the path to your menu icon image
                                        width=30,
                                        height=30,
                                        fit=ft.ImageFit.CONTAIN,
                                    ),
                                    style=ft.ButtonStyle(
                                        padding=ft.Padding(5, 5, 5, 5),
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                    ),
                                ),
                                ft.Image(src="agos_logo.png", width=300, fit=ft.ImageFit.CONTAIN),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.Padding(10, 0, 10, 0),
                        height=60,
                    ),
                    # Forgot Password UI Flow
                    ft.Container(
                        content=ft.Column(
                            [
                                step1_container,  # Email Input
                                step2_container,  # Pin Input (visible after email confirmation)
                                step3_container,  # New Password Input (visible after pin confirmation)
                            ],
                            spacing=20,
                        ),
                        padding=20,
                    ),
                ],
                spacing=20,
            ),
            padding=20,
        )

    def show_editContent(e):
        page.clean()
        page.add(edit_content_page())
        page.update()

    def show_addAccount(e):
        page.clean()
        page.add(add_account())
        page.update()

    def show_forgotPassword(e):
        page.clean()
        page.add(forgot_password())
        page.update()

    def show_editProfile(e):
        page.clean()
        page.add(edit_profile_page())
        page.update()

    def show_notification(e):
        """
        Handles the display of the notification page when the notification icon is clicked.
        """
        # Clear the current page content
        page.clean()

        # Add the notification page content
        page.add(notification_page())

        # Update the page to reflect changes
        page.update()

    def show_signup(e):
        page.clean()
        page.add(signup_view())
        page.update()

    def show_createprofile(e):
        page.clean()
        page.add(create_profile())
        page.update()

    def show_signin(e):
        page.clean()
        page.add(signin_view())
        page.update()

    def show_userpage(e):
        page.clean()  # Clear the current page content
        user_pg = user_page()  # Ensure this function returns a valid component
        if user_pg is not None:
            page.add(user_pg)  # Only add if user_pg is valid
        else:
            print("Error: user_page() returned None")  # Debugging message
        page.update()  # Refresh the page

    def show_adminpage(e):
        page.clean()  # Clear the current page content
        admin_pg = admin_page()  # Ensure this function returns a valid component
        if admin_pg is not None:
            page.add(admin_pg)  # Only add if user_pg is valid
        else:
            print("Error: admin_page() returned None")  # Debugging message
        page.update()  # Refresh the page

    def hide_sidebar():
        nonlocal sidebar_visible
        sidebar_visible = False
        sidebar_container.visible = sidebar_visible  # Hide the sidebar container
        page.update()  # Refresh the page

    def loading_screen():
        page.clean()
        page.add(ft.Container(
            content=ft.Image(src="agos_logo.png", width=200, height=500, fit=ft.ImageFit.CONTAIN),
            alignment=ft.alignment.center
        ))
        page.update()
        time.sleep(2)  # Delay before moving to the sign-in page
        page.clean()
        page.add(signin_view())
        page.update()

    loading_screen()

    content_store = {
        "tipid_tips": {
            "label": "Tipid Tips",
            "icon": "tipid_tips_icon.png",
            "type": "detailed_list",
            "content": [
                {"title": "Fix Leaks", "description": "Even small drips waste liters of water. Repair them quickly."},
                {"title": "Turn Off Taps",
                 "description": "Don’t leave water running when brushing, washing, or soaping up."},
                {"title": "Collect Rainwater", "description": "Use rainwater for watering plants or cleaning."},
                {"title": "Use a Bucket for Washing",
                 "description": "A bucket is more water-efficient than a hose for cleaning cars or outdoor spaces."},
                {"title": "Water Plants Early or Late",
                 "description": "Water in the morning or evening to reduce evaporation."},
                {"title": "Do Full Laundry Loads", "description": "Wash only full loads to save water and energy."},
                {"title": "Reuse Water",
                 "description": "Use leftover water from washing fruits or veggies for plants."},
                {"title": "Spread the Word", "description": "Share these tips to inspire others to save water."},
            ],
        },
        "safe_water": {
            "label": "Safe Water",
            "icon": "safe_water_icon.png",
            "type": "detailed_list",
            "content": [
                {"title": "Maintain Proper Water Storage",
                 "description": "Keep containers sealed to prevent contamination."},
                {"title": "Boil Water When in Doubt", "description": "Boiling kills bacteria and viruses."},
                {"title": "Test Water Quality Regularly",
                 "description": "Conduct regular tests for key water quality indicators such as pH, chlorine, nitrates, and heavy metals to ensure the water is safe for consumption."},
                {"title": "Keep Pipes Clean and Well-Maintained",
                 "description": "Inspect and clean plumbing pipes regularly to prevent the buildup of contaminants and ensure a steady flow of safe water."},
                {"title": "Keep Water Tanks Covered",
                 "description": "If you use a water storage tank, ensure it is properly sealed and covered to prevent contamination from dust, insects, or animals."},
            ],
        },
        "water_level": {
            "label": "Water Level",
            "icon": "water_monitor_icon.png",
            "type": "water",
            "content": {"level": 75},
        },
        "interruption": {
            "label": "Interruption",
            "icon": "interruption_icon.png",
            "type": "text",
            "content": "Stay updated on water interruptions in your area.",
        },
    }

    notifications = [
        {"id": 1, "title": "System Update", "content": "Scheduled maintenance at 3 PM", "read": False},
        {"id": 2, "title": "New Policy", "content": "Updated water usage policy", "read": True},
        {"id": 3, "title": "Reminder", "content": "Submit your monthly report", "read": False},
    ]

    def fetch_notifications_from_db():
        """
        Fetch notifications from the database.
        """
        try:
            cursor = db.cursor(dictionary=True)  # Use dictionary cursor for easier handling
            cursor.execute("SELECT id, title, content, unread FROM notifications ORDER BY id DESC")
            notifications = cursor.fetchall()
            return notifications
        except mysql.connector.Error as e:
            print(f"Error fetching notifications: {e}")
            return []
        finally:
            cursor.close()

    def mark_notification_as_read_in_db(notification_id):
        """
        Mark a notification as read in the database.
        """
        try:
            cursor = db.cursor()
            cursor.execute("UPDATE notifications SET unread = 0 WHERE id = %s", (notification_id,))
            db.commit()
        except mysql.connector.Error as e:
            print(f"Error updating notification: {e}")
        finally:
            cursor.close()

    def delete_notification_from_db(notification_id):
        """
        Delete a notification from the database.
        """
        try:
            cursor = db.cursor()
            cursor.execute("DELETE FROM notifications WHERE id = %s", (notification_id,))
            db.commit()
        except mysql.connector.Error as e:
            print(f"Error deleting notification: {e}")
        finally:
            cursor.close()

    def notification_page():
        """
        Notification Page: Displays a list of notifications with management options.
        """
        notifications = fetch_notifications_from_db()  # Fetch notifications from the database

        def mark_as_read(notification_id):
            """
            Mark a notification as read.
            """
            mark_notification_as_read_in_db(notification_id)
            # Refresh the notifications list
            nonlocal notifications
            notifications = fetch_notifications_from_db()
            page.update()

        def delete_notification(notification_id):
            """
            Delete a notification.
            """
            delete_notification_from_db(notification_id)
            # Refresh the notifications list
            nonlocal notifications
            notifications = fetch_notifications_from_db()
            page.update()

        def render_notifications():
            """
            Render the list of notifications dynamically.
            """
            return [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(notification["title"], size=18, weight="bold", color="blue"),
                            ft.Text(notification["content"], size=14, color="black"),
                            ft.Row(
                                [
                                    ft.ElevatedButton(
                                        "Mark as Read",
                                        on_click=lambda e, nid=notification["id"]: mark_as_read(nid),
                                        bgcolor="green",
                                        color="white",
                                        visible=notification["unread"],  # Show only if unread
                                    ),
                                    ft.ElevatedButton(
                                        "Delete",
                                        on_click=lambda e, nid=notification["id"]: delete_notification(nid),
                                        bgcolor="red",
                                        color="white",
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.START,
                                spacing=10,
                            ),
                        ],
                        spacing=5,
                    ),
                    padding=15,
                    margin=ft.Margin(10, 5, 10, 5),
                    bgcolor="#F6F4F1" if not notification["unread"] else "#AFDBF5",
                    border_radius=10,
                )
                for notification in notifications
            ]

        return ft.Container(
            content=ft.Column(
                [
                    # Navigation Bar
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.ElevatedButton(
                                    on_click=show_userpage,
                                    content=ft.Image(
                                        src="back.png",
                                        width=30,
                                        height=30,
                                        fit=ft.ImageFit.CONTAIN,
                                    ),
                                    style=ft.ButtonStyle(
                                        padding=ft.Padding(5, 5, 5, 5),
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                    ),
                                ),
                                ft.Image(
                                    src="agos_logo.png", width=300, fit=ft.ImageFit.CONTAIN
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.Padding(10, 0, 10, 0),
                        height=60,
                    ),
                    # Header
                    ft.Container(
                        content=ft.Text("Notifications", size=24, weight="bold", color="blue"),
                        padding=15,
                        border_radius=10,
                    ),
                    ft.Divider(),
                    # Notifications List
                    ft.Column(
                        render_notifications(),
                        spacing=10,
                    ),
                ],
                spacing=15,
            ),
            padding=20,
        )

    def get_unread_count():
        """
        Get the count of unread notifications from the database.
        """
        try:
            cursor = db.cursor()
            cursor.execute("SELECT COUNT(*) FROM notifications WHERE unread = 1")
            count = cursor.fetchone()[0]
            return count
        except mysql.connector.Error as e:
            print(f"Error fetching unread notifications count: {e}")
            return 0
        finally:
            cursor.close()
    def edit_content_page():
        # Fetch content from the database
        def fetch_content_store():
            """Fetch content from the database."""
            cursor.execute("SELECT details, time_date, location FROM tbl_water_interruptions")
            rows = cursor.fetchall()
            # Use time_date (row[1]) as the feature key
            return {row[1]: {"label": row[2], "content": row[0]} for row in rows}

        # Update a specific field in the database
        def update_database(feature_key, field, value):
            """Update a specific field in the database."""
            field_mapping = {
                "content": "details",  # Content updates the 'details' column
                "label": "location",  # Label updates the 'location' column
                "feature": "time_date"  # Feature updates the 'time_date' column
            }
            db_field = field_mapping.get(field)
            if db_field:
                query = f"UPDATE tbl_water_interruptions SET {db_field} = %s WHERE time_date = %s"
                cursor.execute(query, (value, feature_key))
                db.commit()
            else:
                print(f"Invalid field: {field}")

        # Delete a row from the database
        def delete_row(feature_key):
            """Delete a row from the database."""
            query = "DELETE FROM tbl_water_interruptions WHERE time_date = %s"
            cursor.execute(query, (feature_key,))
            db.commit()
            content_store.pop(feature_key, None)  # Remove the entry from the content store
            page.snack_bar = ft.SnackBar(ft.Text(f"Row '{feature_key}' updated successfully!"))
            page.snack_bar.open()
            page.update()

        # Save changes for a specific row
        def save_row(feature_key):
            """Save changes for a specific row."""
            print(f"Saving row: {feature_key}")
            # Update fields in the database
            for field in content_store[feature_key]:
                update_database(feature_key, field, content_store[feature_key][field])
            page.snack_bar = ft.SnackBar(ft.Text(f"Row '{feature_key}' updated successfully!"))
            page.snack_bar.open = True

        # Update the content store and database
        def update_content_store(feature_key, field, value):
            """Update the content store and database."""
            if feature_key in content_store:
                content_store[feature_key][field] = value
                page.update()

        # Notify the admin that changes were saved
        def save_changes(e):
            """Save all changes made by the admin."""
            print("Updated Content Store:", content_store)  # For debugging
            page.snack_bar = ft.SnackBar(ft.Text("All changes updated successfully!"))
            page.snack_bar.open()

        # Initialize content store
        content_store = fetch_content_store()

        # Build and return the content editing UI
        return ft.Container(
            content=ft.Column(
                [
                    # Navigation Bar
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.ElevatedButton(
                                    on_click=show_adminpage,
                                    content=ft.Image(
                                        src="back.png", width=30, height=30, fit=ft.ImageFit.CONTAIN
                                    ),
                                    style=ft.ButtonStyle(
                                        padding=ft.Padding(0, 0, 0, 0),
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                    ),
                                ),
                                ft.Image(
                                    src="agos_logo.png", width=500, fit=ft.ImageFit.CONTAIN
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.Padding(10, 0, 10, 0),
                        height=60,
                    ),
                    # Edit User Page Content
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "Edit User Page Content",
                                    size=24,
                                    weight="bold",
                                    color="blue",
                                ),
                                ft.Divider(),
                                # Iterate through content_store to generate dynamic fields
                                *[
                                    ft.Column(
                                        [
                                            ft.Text(f"Feature: {key}", size=18, weight="bold"),
                                            ft.TextField(
                                                label="Content",
                                                value=feature.get("content", ""),
                                                on_change=lambda e, k=key: update_content_store(
                                                    k, "content", e.control.value
                                                ),
                                            ),
                                            ft.TextField(
                                                label="Label",
                                                value=str(feature.get("label", "")),
                                                on_change=lambda e, k=key: update_content_store(
                                                    k, "label", e.control.value
                                                ),
                                            ),
                                            ft.Row(
                                                [
                                                    ft.ElevatedButton(
                                                        "Save",
                                                        on_click=lambda e, k=key: save_row(k),
                                                    ),
                                                    ft.ElevatedButton(
                                                        "Delete",
                                                        on_click=lambda e, k=key: delete_row(k),
                                                        style=ft.ButtonStyle(
                                                            bgcolor="red",
                                                            color="white",
                                                        ),
                                                    ),
                                                ],
                                                spacing=10,
                                            ),
                                            ft.Divider(),
                                        ]
                                    )
                                    for key, feature in content_store.items()
                                ],
                                ft.ElevatedButton("Save All Changes", on_click=save_changes),
                            ],
                            spacing=10,
                        ),
                        padding=20,
                        border_radius=10,
                    ),
                ],
                spacing=10,
            ),
        )

    def edit_profile_page():
        """
        Edit Profile Page: Allows a user to update their name, address, and age.
        """
        # Placeholder for storing user information
        user_profile = {
            "name": "John Doe",
            "address": "123 Main Street",
            "age": "25",
        }

        def update_user_profile(field, value):
            """
            Update the user profile with the new value.
            """
            user_profile[field] = value

        def save_changes(e):
            """
            Save changes made by the user.
            """
            print("Updated Profile:", user_profile)  # For debugging
            page.snack_bar = ft.SnackBar(ft.Text(f"Profile update successfully", bgcolor=ft.colors.RED))
            page.snack_bar.open = True

        return ft.Container(
            content=ft.Column(
                [
                    # Navigation Bar
                    ft.Container(
                        content=ft.Row(
                            [
                                # Back Button
                                ft.ElevatedButton(
                                    on_click=show_userpage,
                                    content=ft.Image(
                                        src="back.png",  # Replace with the path to your menu icon image
                                        width=30,
                                        height=30,
                                        fit=ft.ImageFit.CONTAIN,
                                    ),
                                    style=ft.ButtonStyle(
                                        padding=ft.Padding(0, 0, 0, 0),
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                    ),
                                ),
                                # Logo
                                ft.Image(
                                    src="agos_logo.png", width=300, fit=ft.ImageFit.CONTAIN
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.Padding(10, 0, 10, 0),
                        height=60,
                    ),
                    # Edit Profile Section
                    ft.Container(
                        content=ft.Column(
                            [
                                # Title
                                ft.Text("Edit Profile", size=24, weight="bold", color="blue"),
                                ft.Divider(),
                                # Name Field
                                ft.TextField(
                                    label="Name",
                                    value=user_profile["name"],
                                    on_change=lambda e: update_user_profile(
                                        "name", e.control.value
                                    ),
                                ),
                                # Address Field
                                ft.TextField(
                                    label="Address",
                                    value=user_profile["address"],
                                    on_change=lambda e: update_user_profile(
                                        "address", e.control.value
                                    ),
                                ),
                                # Age Field
                                ft.TextField(
                                    label="Age",
                                    value=user_profile["age"],
                                    on_change=lambda e: update_user_profile(
                                        "age", e.control.value
                                    ),
                                    keyboard_type=ft.KeyboardType.NUMBER,  # Restrict input to numbers
                                ),
                                ft.Divider(),
                                # Save Button
                                ft.ElevatedButton("Save Changes", on_click=save_changes),
                            ],
                            spacing=10,
                        ),
                        padding=20,
                        border_radius=10,
                    ),
                ],
                spacing=10,
            ),
            padding=20,
        )

    def add_account():
        """
        Add Account Page: Allows an admin or user to create a new account.
        """

        # Placeholder for storing account information
        new_account = {
            "username": "",
            "email": "",
            "password": "",
            "role": "user",  # Default role
            "profile_status": "incomplete",  # Default profile status
        }

        def update_new_account(field, value):
            """
            Update the new account information with the specified field and value.
            """
            new_account[field] = value

        def hash_password(password):
            """
            Hash the password using bcrypt.
            """
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed

        def save_new_account(e):
            """
            Save the new account to the database or update role if the email already exists.
            """
            email = new_account["email"]
            username = new_account["username"]
            password = new_account["password"]
            role = new_account["role"]

            # Hash the password
            hashed_password = hash_password(password)

            # Check if the email already exists
            cursor.execute("SELECT COUNT(*) FROM tbl_user_account WHERE email = %s", (email,))
            email_exists = cursor.fetchone()[0] > 0

            if email_exists:
                # Update the role to admin for the existing account
                cursor.execute(
                    "UPDATE tbl_user_account SET role = %s WHERE email = %s",
                    (role, email),
                )
                db.commit()
                page.snack_bar = ft.SnackBar(ft.Text("Role updated to admin for the existing account!"))
            else:
                # Insert the new account into the database
                cursor.execute(
                    """
                    INSERT INTO tbl_user_account (username, email, password, role, profile_status)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (username, email, hashed_password.decode('utf-8'), role, new_account["profile_status"]),
                )
                db.commit()
                page.snack_bar = ft.SnackBar(ft.Text("Account added successfully!"))

            # Show the snackbar notification
            page.snack_bar.open()

        return ft.Container(
            content=ft.Column(
                [
                    # Navigation Bar
                    ft.Container(
                        content=ft.Row(
                            [
                                # Back Button
                                ft.ElevatedButton(
                                    on_click=show_adminpage,  # Replace with the appropriate navigation function
                                    content=ft.Image(
                                        src="back.png",  # Replace with the path to your back button image
                                        width=30,
                                        height=30,
                                        fit=ft.ImageFit.CONTAIN,
                                    ),
                                    style=ft.ButtonStyle(
                                        padding=ft.Padding(0, 0, 0, 0),
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                    ),
                                ),
                                # Logo
                                ft.Image(
                                    src="agos_logo.png", width=300, fit=ft.ImageFit.CONTAIN
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.Padding(10, 0, 10, 0),
                        height=60,
                    ),
                    # Add Account Section
                    ft.Container(
                        content=ft.Column(
                            [
                                # Title
                                ft.Text("Add Account", size=24, weight="bold", color="blue"),
                                ft.Divider(),
                                # Username Field
                                ft.TextField(
                                    label="Username",
                                    on_change=lambda e: update_new_account(
                                        "username", e.control.value
                                    ),
                                ),
                                # Email Field
                                ft.TextField(
                                    label="Email",
                                    on_change=lambda e: update_new_account(
                                        "email", e.control.value
                                    ),
                                    keyboard_type=ft.KeyboardType.EMAIL,
                                ),
                                # Password Field
                                ft.TextField(
                                    label="Password",
                                    password=True,
                                    on_change=lambda e: update_new_account(
                                        "password", e.control.value
                                    ),
                                ),
                                # Role Dropdown
                                ft.Dropdown(
                                    label="Role",
                                    options=[
                                        ft.dropdown.Option("admin"),
                                        ft.dropdown.Option("user"),
                                    ],
                                    value="user",  # Default role
                                    on_change=lambda e: update_new_account(
                                        "role", e.control.value
                                    ),
                                ),
                                ft.Divider(),
                                # Save Button
                                ft.ElevatedButton(
                                    "Add Account",
                                    on_click=save_new_account,
                                    style=ft.ButtonStyle(bgcolor=ft.colors.GREEN),
                                ),
                            ],
                            spacing=10,
                        ),
                        padding=20,
                        border_radius=10,
                    ),
                ],
                spacing=10,
            ),
            padding=20,
        )

    def admin_page():

        def app_barAdmin():
            return ft.Container(
                content=ft.Row(
                    [
                        ft.ElevatedButton(
                            on_click=toggle_sidebar,
                            content=ft.Image(
                                src="menu_icon.png",  # Replace with the path to your menu icon image
                                width=30,
                                height=30,
                                fit=ft.ImageFit.CONTAIN,
                            ),
                            style=ft.ButtonStyle(
                                padding=ft.Padding(left=0, top=0, right=0, bottom=0),  # Correct padding format
                                shape=ft.RoundedRectangleBorder(radius=8),  # Optional: to make the button rounded
                            ),
                        ),
                        ft.Image(
                            src="agos_logo.png", width=100, fit=ft.ImageFit.CONTAIN
                        ),
                        ft.ElevatedButton(
                            on_click=lambda e: print("Notification clicked"),
                            content=ft.Image(
                                src="notification_icon.png",  # Replace with the path to your notification icon image
                                width=30,
                                height=30,
                                fit=ft.ImageFit.CONTAIN,
                            ),
                            style=ft.ButtonStyle(
                                padding=ft.Padding(left=0, top=0, right=0, bottom=0),  # Correct padding format
                                shape=ft.RoundedRectangleBorder(radius=8),  # Optional: to make the button rounded
                            ),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),

                padding=ft.Padding(left=10, top=0, right=10, bottom=0),  # Correct padding format
                height=60,
            )

        def user_greetingAdmin():
            return ft.Container(
                ft.Row(
                    [
                        ft.Text("Hello,", size=20, weight="bold", color="white"),
                        ft.Text("Admin", size=25, weight="bold", color="white"),
                        ft.Image(
                            src="happy_icon.png",
                            width=40,
                            height=40,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#00adef",
                padding=ft.Padding(left=20, top=10, right=20, bottom=10),  # Correct padding format
                alignment=ft.alignment.center_left,
                height=100,
                border_radius=ft.border_radius.all(20),
            )

        # Function to post water interruption
        # List of water interruptions for display
        # List to temporarily hold water interruptions from the database
        water_interruptions = []

        def fetch_water_interruptions():
            """Fetch all water interruptions from the database."""
            global water_interruptions
            try:
                # Query to fetch all interruptions
                cursor.execute("SELECT id, details, time_date, location FROM tbl_water_interruptions")
                results = cursor.fetchall()

                # Update local list
                water_interruptions = [
                    {"id": row[0], "details": row[1], "time_date": row[2], "location": row[3]}
                    for row in results
                ]
                update_display()  # Refresh the display
            except mysql.connector.Error as err:
                print(f"Database error: {err}")

        def delete_water_interruption(interruption_id):
            """Delete a specific water interruption by ID."""
            try:
                # Delete query
                cursor.execute("DELETE FROM tbl_water_interruptions WHERE id = %s", (interruption_id,))
                db.commit()  # Commit the deletion

                # Refresh the interruptions list and display
                fetch_water_interruptions()
            except mysql.connector.Error as err:
                print(f"Database error: {err}")

        def post_water_interruption(e):
            """Add a new water interruption to the database."""
            interruption_text = interruption_input.value
            time_date = interruption_timeDate.value
            location = interruption_location.value

            if interruption_text and time_date and location:  # Ensure all fields are filled
                try:
                    # SQL query to insert a new interruption
                    query = """
                        INSERT INTO tbl_water_interruptions (details, time_date, location)
                        VALUES (%s, %s, %s)
                    """
                    values = (interruption_text, time_date, location)

                    cursor.execute(query, values)  # Execute query with parameterized values
                    db.commit()  # Commit changes to the database

                    # Clear input fields
                    interruption_input.value = ""
                    interruption_timeDate.value = ""
                    interruption_location.value = ""

                    # Refresh the display
                    fetch_water_interruptions()
                    page.update()
                except mysql.connector.Error as err:
                    print(f"Database error: {err}")
            else:
                print("All fields are required.")

        def update_display():
            """Update the display with interruptions from the database."""
            interruption_display.controls = [
                ft.Row(
                    [
                        ft.Text(
                            f"{interruption['time_date']} - {interruption['location']}: {interruption['details']}",
                            size=14,
                            color="#333333",
                        ),
                        ft.IconButton(
                            icon=ft.icons.DELETE,
                            tooltip="Delete",
                            on_click=lambda e, interruption_id=interruption["id"]: delete_water_interruption(
                                interruption_id),
                            icon_color="red",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
                for interruption in water_interruptions
            ]
            page.update()

        # Water Interruption Input Fields
        interruption_input = ft.TextField(
            label="Post Water Interruption",
            hint_text="Enter details about water interruption",
            width="100%",
        )

        interruption_timeDate = ft.TextField(
            label="Enter Time and Date",
            hint_text="Enter details about time and date",
            width="100%",
        )

        interruption_location = ft.TextField(
            label="Location",
            hint_text="Enter Location",
            width="100%",
        )

        # Button to post water interruption
        post_button = ft.Container(
            content=ft.ElevatedButton(
                "Post",
                on_click=post_water_interruption,
                bgcolor="#057ee6",
                color="white",
                width=500,  # Fixed width
            ),
            alignment=ft.alignment.center,  # Centers the button
        )

        # Display posted water interruptions
        interruption_display = ft.Column(
            [],
            spacing=5,
        )

        # Fetch interruptions from the database initially
        fetch_water_interruptions()
        # The rest of your UI code (sidebar, layout, etc.) remains unchanged.

        # Updated Sidebar Content
        sidebar_container.content = ft.Column(
            [
                ft.Container(
                    content=ft.IconButton(
                        icon=ft.icons.CLOSE,
                        on_click=lambda e: [close_sidebar(e), show_adminpage()],
                        tooltip="Close Sidebar",
                        bgcolor="red"
                    ),
                    alignment=ft.alignment.top_right,
                    padding=ft.Padding(10, 10, 10, 0),
                ),
                ft.Image(src="agos_logo_white.png", width=float('inf'), height=150),
                ft.Container(
                    content=ft.ElevatedButton(
                        "Home",
                        on_click=lambda e: [show_adminpage(e), hide_sidebar()],
                        bgcolor="white",
                        width=float('inf'),

                    ),
                    border_radius=10,
                ),
                ft.Container(
                    content=ft.ElevatedButton(
                        "Edit Content",
                        on_click=lambda e: [show_editContent(e), hide_sidebar()],
                        bgcolor="white",
                        width=float('inf')
                    ),
                    border_radius=10,
                ),
                ft.Container(
                    content=ft.ElevatedButton(
                        "Add Account",
                        on_click=lambda e: [show_addAccount(e), hide_sidebar()],
                        bgcolor="white",
                        width=float('inf')
                    ),
                    border_radius=10,
                ),
                ft.Container(
                    content=ft.ElevatedButton(
                        "Logout",
                        on_click=logout_confirmation,
                        bgcolor=ft.colors.RED,
                        width=float('inf')
                    ),
                    border_radius=10,
                )
            ],
            spacing=10,
            alignment=ft.alignment.center
        )

        # Function to close the sidebar
        def close_sidebar(event):
            sidebar_container.visible = False
            page.update()

        # Page Layout
        page.clean()
        page.add(
            ft.Stack(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    app_barAdmin(),
                                    user_greetingAdmin(),
                                    ft.Container(  # Wrapping the column in a container for centering
                                        content=ft.Column(
                                            [
                                                ft.Text("Water Level", size=24, weight="bold"),
                                                chart_container,  # Displaying the donut chart here

                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER,  # Center content vertically
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                            # Center content horizontally
                                            spacing=20,
                                        ),
                                        alignment=ft.alignment.center,  # Centering the column
                                        expand=True,  # Ensuring it expands to fill the space
                                    ),
                                    ft.Divider(),
                                    ft.Text("Water Interruptions", size=24, weight="bold"),
                                    ft.Column(
                                        [interruption_input, interruption_timeDate, interruption_location, post_button],
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        spacing=10,
                                    ),
                                    ft.Divider(),
                                    interruption_display,
                                ],
                                expand=True,
                            ),
                        ],
                        expand=True,
                        alignment=ft.MainAxisAlignment.CENTER,  # Centering the row content
                    ),
                    sidebar_container,  # Sidebar added to the stack with z_index
                ]
            )
        )
        chart_container.content = update_chart()
        threading.Thread(target=refresh_chart, daemon=True).start()

    # State for sidebar visibility
    sidebar_visible = False

    # Initialize sidebar container
    sidebar_container = ft.Container(
        visible=False,  # Initially hidden
        expand=True,
        bgcolor="#87cefa",
        width="100%",
        height="100%",
        padding=ft.Padding(20, 20, 20, page.height),
    )
    sidebar_container.z_index = 100
    sidebar_container.width = "100%"  # Full-page width
    sidebar_container.height = page.window_max_height  # Full-page height  # Set the z-index after initializing

    # Toggle sidebar visibility function
    def toggle_sidebar(e):
        nonlocal sidebar_visible
        sidebar_visible = not sidebar_visible  # Toggle the visibility state
        sidebar_container.visible = sidebar_visible
        page.update()

    def user_page():
        def app_bar():
            """
            Returns the app bar with a menu button, logo, and notification icon with badge.
            """
            return ft.Container(
                content=ft.Row(
                    [
                        # Menu button
                        ft.ElevatedButton(
                            on_click=toggle_sidebar,
                            content=ft.Image(
                                src="menu_icon.png",  # Path to your menu icon image
                                width=30,
                                height=30,
                                fit=ft.ImageFit.CONTAIN,
                            ),
                            style=ft.ButtonStyle(
                                padding=ft.Padding(left=0, top=0, right=0, bottom=0),
                                shape=ft.RoundedRectangleBorder(radius=8),
                            ),
                        ),
                        # Logo
                        ft.Image(
                            src="agos_logo.png",
                            width=100,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        # Notification icon with unread badge
                        ft.Stack(
                            [
                                # Notification icon
                                ft.ElevatedButton(
                                    on_click=lambda e: show_notification(e),  # Navigate to notification page
                                    content=ft.Image(
                                        src="notification_icon.png",  # Path to notification icon image
                                        width=30,
                                        height=30,
                                        fit=ft.ImageFit.CONTAIN,
                                    ),
                                    style=ft.ButtonStyle(
                                        padding=ft.Padding(left=0, top=0, right=0, bottom=0),
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                    ),
                                ),
                                # Badge for unread notifications
                                ft.Container(
                                    content=ft.Text(
                                        str(get_unread_count()),  # Display unread count dynamically
                                        size=12,
                                        weight="bold",
                                        color="white",
                                    ),
                                    bgcolor="red",
                                    padding=ft.Padding(left=5, top=2, right=5, bottom=2),
                                    border_radius=10,
                                    alignment=ft.Alignment(1, -1),  # Top-right corner of the ElevatedButton
                                    width=20,  # Set a fixed width for the badge
                                    height=20,  # Set a fixed height for the badge
                                    visible=get_unread_count() > 0,  # Show badge only if there are unread notifications
                                ),
                            ]
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(left=10, top=0, right=10, bottom=0),
                height=60,
            )

        def user_greeting():
            return ft.Container(
                ft.Row(
                    [
                        ft.Text("Hello,", size=20, weight="bold", color="white"),
                        ft.Text("User", size=25, weight="bold", color="white"),
                        ft.Image(
                            src="happy_icon.png",
                            width=40,
                            height=40,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#00adef",
                padding=ft.Padding(left=20, top=10, right=20, bottom=10),  # Correct padding format
                alignment=ft.alignment.center_left,
                height=100,
                border_radius=ft.border_radius.all(20),
            )

        # Updated Sidebar Content
        sidebar_container.content = ft.Column(
            [
                ft.Container(
                    content=ft.IconButton(
                        icon=ft.icons.CLOSE,
                        on_click=lambda e: close_sidebar(e),
                        tooltip="Close Sidebar",
                        bgcolor="red"
                    ),
                    alignment=ft.alignment.top_right,
                    padding=ft.Padding(10, 10, 10, 0),
                ),
                ft.Image(src="agos_logo_white.png", width=float('inf'), height=150),
                ft.Container(
                    content=ft.ElevatedButton(
                        "Home",
                        on_click=lambda e: [show_userpage(e), hide_sidebar()],
                        bgcolor="white",
                        width=float('inf'),

                    ),
                    border_radius=10,
                ),
                ft.Container(
                    content=ft.ElevatedButton(
                        "Profile",
                        on_click=lambda e: [show_editProfile(e), hide_sidebar()],
                        bgcolor="white",
                        width=float('inf')
                    ),
                    border_radius=10,
                ),
                ft.Container(
                    content=ft.ElevatedButton(
                        "Logout",
                        on_click=logout_confirmation,
                        bgcolor=ft.colors.RED,
                        width=float('inf')
                    ),
                    border_radius=10,
                )
            ],
            spacing=10,
            alignment=ft.alignment.center
        )

        # Function to close the sidebar
        def close_sidebar(event):
            sidebar_container.visible = False
            page.update()

        def update_content(feature_key):
            """
            Updates the main content area based on the selected feature.
            """
            feature = content_store.get(feature_key, {})

            if feature.get("type") == "detailed_list" and "content" in feature:
                # Detailed list content
                content_text.content = ft.Column(
                    [
                        ft.Text(feature["label"], size=22, weight="bold", color="#057ee6"),
                        ft.Column(
                            [
                                ft.Column(
                                    [
                                        ft.Text(item["title"], size=18, weight="bold", color="#057ee6"),
                                        ft.Text(item["description"], size=14, color="#333333"),
                                    ],
                                    spacing=5,
                                )
                                for item in feature["content"]
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=15,
                )
            elif feature.get("type") == "water":
                # Water level content
                water_level = get_water_level_from_db()
                content_text.content = ft.Column(
                    [
                        ft.Text(feature["label"], size=22, weight="bold", color="#057ee6"),
                        create_donut_chart(water_level),
                    ],
                    spacing=15,
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            elif feature.get("type") == "text":
                # Fetch water interruption data from the database
                water_interruptions = get_water_interruptions_from_db()
                print(water_interruptions)
                if water_interruptions:
                    # Display the water interruption data in the UI
                    content_text.content = ft.Column(
                        [
                            ft.Text(feature["label"], size=22, weight="bold", color="#057ee6"),
                        ] + [
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            f"Location:               {item['location']}\n"
                                            f"Date:                     {item['time_date']}\n"
                                            f"Details:                  {item['details']}",
                                            size=18,  # Base size
                                            color="black",
                                            weight="bold",
                                            text_align="left"
                                        )
                                    ],
                                ),
                            )
                            for item in water_interruptions
                        ],
                        spacing=15,
                        alignment=ft.MainAxisAlignment.CENTER,
                    )
                else:
                    # Handle empty data case with a fallback message
                    content_text.content = ft.Column(
                        [
                            ft.Text(feature["label"], size=22, weight="bold", color="#057ee6"),
                            ft.Text("No water interruptions at the moment.", size=16, color="#555"),
                        ],
                        spacing=15,
                    )
            else:
                # Unsupported type or no data available
                content_text.content = ft.Text(
                    "Content type not supported or no water interruptions reported.",
                    size=16,
                    color="#555",
                    text_align="center",
                )

            page.update()

        # Feature buttons
        buttons = [
            ft.Column(
                [
                    ft.Container(
                        ft.Image(
                            src=feature["icon"],
                            width=50,
                            height=50,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        width=80,
                        height=80,
                        bgcolor="#cce1f1",
                        border_radius=ft.border_radius.all(8),
                        alignment=ft.alignment.center,
                        on_click=lambda e, feature_key=key: update_content(feature_key),
                    ),
                    ft.Text(
                        feature["label"],
                        size=12,
                        weight="bold",
                        color="#057ee6"
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=5,
            )
            for key, feature in content_store.items()
        ]

        # Create a row for the feature buttons
        feature_buttons = ft.Row(
            buttons,
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            wrap=True,
            spacing=10,
            run_spacing=10,
        )

        # Content section (initially empty or default message)
        content_text = ft.Container(
            content=ft.Text(
                "Welcome to Agos",
                size=30,
                weight="bold",
                color="black",
                text_align="center",
            ),
            bgcolor=ft.colors.WHITE,
            border_radius=ft.border_radius.all(20),
            alignment=ft.alignment.center,
            padding=ft.Padding(20, 20, 20, 20),
        )

        # Create a blue outer container to wrap the content_section
        outer_container = ft.Container(
            content=content_text,
            bgcolor=ft.colors.BLUE,
            padding=ft.Padding(10, 40, 10, 40),
            border_radius=ft.border_radius.all(20),
            alignment=ft.alignment.center,
            margin=ft.Margin(left=10, top=20, right=10, bottom=20),
        )

        # Page Layout
        page.clean()
        page.add(
            ft.Stack(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    app_bar(),
                                    user_greeting(),
                                    ft.Container(
                                        feature_buttons,
                                        padding=ft.Padding(20, 10, 20, 10),
                                        alignment=ft.alignment.center,
                                    ),
                                    outer_container,
                                ],
                                expand=True,
                            ),
                        ],
                        expand=True,
                    ),
                    sidebar_container,
                ]
            )
        )
        page.update()


ft.app(target=main)
