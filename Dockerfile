FROM mcr.microsoft.com/playwright:v1.58.2-noble

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-pip \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY requirements.txt ./
RUN python3 -m pip install --break-system-packages --no-cache-dir -r requirements.txt

COPY . .

ENV HOST=0.0.0.0
ENV PORT=10000
ENV CODE2VIDEO_NO_BROWSER=1

EXPOSE 10000

CMD ["python3", "server.py"]
