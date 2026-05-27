# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  🐳 Dockerfile - ربات مانیتور گروه تلگرام
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FROM python:3.12-slim

# ─── متادیتا ───
LABEL maintainer="Telegram Group Monitor Bot"
LABEL description="ربات مانیتور و گزارش‌گیری فعالیت‌های گروه تلگرام"
LABEL version="1.0.0"

# ─── تنظیمات ───
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Tehran

WORKDIR /app

# ─── نصب وابستگی‌ها ───
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── کپی کد ───
COPY . .

# ─── ساخت پوشه دیتابیس ───
RUN mkdir -p data

# ─── اجرا ───
CMD ["python", "main.py"]
