FROM hydrokhoos/ndn-all

# 必要なパッケージのインストール
RUN apt-get update && apt-get install -y \
    python3-pip \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# python-ndnのインストール
RUN pip3 install python-ndn pycryptodome

# 作業ディレクトリの設定
WORKDIR /app

# ソースコードをコンテナ内にコピー
COPY . /app/
