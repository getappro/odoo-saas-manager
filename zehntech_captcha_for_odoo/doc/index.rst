Website Captcha for Odoo
================================================================

The **Website Captcha for Odoo** module enhances security by adding customizable captcha verification to critical website forms. Protect your Odoo website from spam, bots, and automated attacks with multiple captcha types — Mathematical, Numeric Image, and Alphabetic Image — all configurable to meet your specific security needs.

**Table of Contents**
======================
.. contents::
    :local:

**Key Features**
================================================================

1. **Multiple Captcha Types**

   Choose the captcha style that best fits your security and user experience requirements. Select from Mathematical Captcha (solve simple math problems), Numeric Image Captcha (type numbers from distorted images), or Alphabetic Image Captcha (type letters from images) — all designed to effectively block bots while remaining user-friendly for legitimate visitors.

2. **Flexible Form Protection**

   Secure the forms that matter most to your business. Enable captcha verification on Login Forms, Signup/Registration Forms, and Password Reset Forms independently or in combination. This granular control ensures you can balance security with user convenience based on each form's risk level.

3. **Highly Customizable Settings**

   Tailor captcha difficulty and appearance to your exact specifications. For Mathematical Captcha, choose operation types (addition, subtraction, multiplication) and number ranges. For Image Captchas, configure length, include/exclude uppercase letters and special symbols, and control distortion levels to find the perfect balance between security and usability.

4. **Multi-Website Support**

   Configure different captcha settings for each website in your Odoo instance. Each website can have its own captcha type, enabled forms, and security parameters, providing flexibility for multi-brand or multi-region deployments with varying security requirements.

5. **Real-Time Preview & Testing**

   See exactly what your users will experience before going live. The built-in preview functionality displays the captcha as it will appear to users, allowing administrators to test different configurations and ensure optimal readability and difficulty before applying changes to production forms.

6. **Seamless Integration with Odoo Security**

   Works harmoniously with Odoo's native authentication and security systems. The module respects existing access rights, user roles, and security policies while adding an additional layer of protection against automated attacks, ensuring a cohesive security architecture.


**Summary**
================================================================

The **Website Captcha for Odoo** module adds robust, customizable captcha verification to login, signup, and password reset forms. With three captcha types (Mathematical, Numeric Image, Alphabetic Image), real-time preview, multi-website support, and flexible configuration options, this module provides comprehensive bot protection while maintaining excellent user experience. Ideal for businesses seeking to enhance website security without compromising usability.

**Installation**
================================================================

1. Clone or download the module from the repository.
2. Place the module in your Odoo addons directory.
3. Restart the Odoo server to update the app list.
4. Install the **Website Captcha for Odoo** module from the Odoo Apps menu.


**Configuration**
================================================================

After installation, configure the captcha settings:

1. Navigate to **Website → Configuration → Settings**.
2. Scroll to the **Captcha** section.
3. Enable captcha by checking the **Enable Captcha** checkbox.
4. Select which forms to protect (Login, Signup, Password Reset).
5. Choose your preferred **Captcha Type** (Mathematical, Numeric Image, or Alphabetic Image).
6. Configure type-specific settings:
   
   * **Mathematical Captcha**: Choose operation type and number range
   * **Numeric Image**: Set length and symbol inclusion
   * **Alphabetic Image**: Configure length, uppercase, and symbols

7. Use the **Refresh Preview** button to see how the captcha will appear.
8. Customize the **Not Verified Message** shown when captcha validation fails.
9. Click **Save** to apply your settings.


**How to Use This Module**
================================================================

Once configured, captchas will automatically appear on the selected forms:

* **For Users**: Simply solve the math problem or type the characters shown in the image before submitting the form.
* **For Administrators**: Monitor and adjust settings as needed. Use the preview feature to test changes before deploying.

The module works transparently in the background, validating captcha responses and preventing form submission when verification fails.


**Technical Details**
================================================================

* **Odoo Version**: 18.0
* **Module Version**: 1.0.0
* **Category**: Website
* **License**: LGPL-3
* **Dependencies**: base, website, web, web_editor, auth_signup
* **Image Generation**: Uses PIL (Pillow) for high-quality captcha image rendering


**Change Logs**
================================================================

[1.0.0]  
---------------------
* ``Added`` [08-12-2025] Initial release of the Website Captcha for Odoo module.

**Support**
================================================================

For technical support, customization requests, or questions about this module:

`Zehntech Technologies <https://www.zehntech.com/erp-crm/odoo-services/>`_

**About Zehntech**

Zehntech Technologies is a leading Odoo implementation partner specializing in ERP/CRM solutions, custom module development, Odoo migration, and comprehensive Odoo services. We help businesses leverage Odoo's full potential with expert consultation and development services.