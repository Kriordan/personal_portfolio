def get_contact_email_content(name, email, message):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Contact Form Submission</title>
    </head>
    <body>
        <table width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: auto;">
            <tr>
                <td style="padding: 20px; text-align: left;">
                    <h1 style="font-family: Arial, sans-serif;">Contact Form Submission</h1>
                    <p style="font-family: Arial, sans-serif;"><strong>Name:</strong> {name}</p>
                    <p style="font-family: Arial, sans-serif;"><strong>Email:</strong> {email}</p>
                    <p style="font-family: Arial, sans-serif;"><strong>Message:</strong></p>
                    <p style="font-family: Arial, sans-serif;">{message}</p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
