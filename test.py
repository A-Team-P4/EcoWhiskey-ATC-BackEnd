import smtplib
with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
    smtp.starttls()
    smtp.login("albertodev421@gmail.com", "boih ftti ihim gzul")
print("OK")
