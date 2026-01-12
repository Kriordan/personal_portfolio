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


def get_password_reset_email_content(reset_url):
    """Generate HTML content for password reset email."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Password Reset Request</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f4f4f4;">
        <table width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <tr>
                <td style="padding: 40px; text-align: center;">
                    <h1 style="font-family: Arial, sans-serif; color: #333333; margin-bottom: 24px;">
                        Password Reset Request
                    </h1>
                    <p style="font-family: Arial, sans-serif; color: #666666; font-size: 16px; line-height: 1.5; margin-bottom: 24px;">
                        You requested a password reset for your account. Click the button below to set a new password.
                    </p>
                    <a href="{reset_url}" style="display: inline-block; padding: 14px 32px; background-color: #007bff; color: #ffffff; text-decoration: none; font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; border-radius: 4px; margin-bottom: 24px;">
                        Reset Password
                    </a>
                    <p style="font-family: Arial, sans-serif; color: #999999; font-size: 14px; line-height: 1.5; margin-top: 24px;">
                        This link will expire in 1 hour. If you didn't request this reset, you can safely ignore this email.
                    </p>
                    <hr style="border: none; border-top: 1px solid #eeeeee; margin: 24px 0;">
                    <p style="font-family: Arial, sans-serif; color: #999999; font-size: 12px;">
                        If the button doesn't work, copy and paste this link into your browser:<br>
                        <a href="{reset_url}" style="color: #007bff; word-break: break-all;">{reset_url}</a>
                    </p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
