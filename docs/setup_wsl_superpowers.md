# 環境構築の手順書(WSL・Claude Code・Superpowers)

所要時間: 30〜60分(再起動1回を含む)。第1回の授業前に済ませておいてください。

| あなたの PC | やること |
|---|---|
| Windows 10 / 11 | **A → B → C → D** の順に全部 |
| macOS / Linux | A は不要。B(ターミナルで実行)→ C → D |

Claude のアカウントは配付済みのものを使います。個人の有料プランや API キーは使わないでください。

---

## A. WSL(Windows 上の Linux)を入れる ― Windows のみ

### A-1. インストール

1. スタートメニューで「PowerShell」を右クリック →「**管理者として実行**」
2. 次を実行:

   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

3. 「再起動してください」と出たら PC を再起動
4. 再起動後に Ubuntu のウィンドウが開くので、**Linux 用のユーザー名とパスワード**を決めて入力
   - ユーザー名は半角英小文字(例: `taro`)
   - パスワードは入力しても画面に何も表示されませんが、入力されています。`sudo` のたびに使うので忘れないこと

### A-2. 確認

PowerShell(管理者でなくてよい)で:

```powershell
wsl -l -v
```

`Ubuntu-24.04` の VERSION が **2** になっていれば成功です。以降は、スタートメニューの「Ubuntu」から開いた画面(以下「Ubuntu ターミナル」)で作業します。

### A-3. うまくいかないとき

| 症状 | 対処 |
|---|---|
| `0x80370102` / 「仮想マシン プラットフォームが…」 | BIOS/UEFI で仮想化(Intel VT-x / AMD-V / SVM)を有効にする。PC のメーカー名 + 「仮想化 有効」で検索 |
| `wsl` コマンドが見つからない | Windows Update を最後まで当ててから再実行 |
| VERSION が 1 | `wsl --set-version Ubuntu-24.04 2` |
| 既に古い Ubuntu が入っている | そのまま使ってよい(22.04 以上なら可) |
| 動作が重い・時刻がずれる | `wsl --shutdown` してから Ubuntu を開き直す |

---

## B. Ubuntu の中に開発ツールを入れる

Ubuntu ターミナルで、1行ずつ実行します(macOS の人は `apt` の行を飛ばしてよい)。

```bash
sudo apt update && sudo apt install -y git curl build-essential
```

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
source ~/.bashrc
uv --version
```

`uv 0.x.x` と表示されれば OK です(Python は uv が自動で用意します)。

Git の名前とメール(授業用のもの)を設定:

```bash
git config --global user.name "Taro Yokosuka"
git config --global user.email "学籍番号@学内ドメイン"
```

---

## C. Claude Code を入れてログインする

> Windows に Claude Code を入れていても、**WSL の中には別途インストール・ログインが必要**です。

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

```bash
source ~/.bashrc
claude --version
```

ログイン:

```bash
claude
```

初回はブラウザが開く(または URL が表示される)ので、**配付された Claude アカウント**でログインします。
WSL でブラウザが開かないときは、表示された URL を Windows のブラウザに貼り付けてください。
ログイン後、`/status` と入力してアカウントが配付されたものになっていることを確認し、`/exit` で終了します。

---

## D. 演習リポジトリを取得して動かす

### D-1. 置き場所の注意

- WSL ではリポジトリを **Linux 側のホーム(`~`)** に置く。`/mnt/c/...`(Windows のフォルダ)に置くと非常に遅くなります
- Windows で直接作業する場合も、**OneDrive の同期フォルダの中には置かない**(`.venv` の同期で壊れやすい)

### D-2. 取得とセットアップ

```bash
cd ~
git clone https://github.com/gappo093/yokosuka_bridge_recovery.git yokosuka-bridge-recovery
cd yokosuka-bridge-recovery
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
python -m pytest
```

`8 passed` と出れば成功です。続けて:

```bash
python scripts/run_baselines.py
```

ベースライン4種のスコア表が出れば準備完了です。

### D-3. VS Code から使う(任意)

1. Windows 側の VS Code に拡張機能「**WSL**」(Microsoft)を入れる
2. Ubuntu ターミナルでリポジトリに移動して `code .`
3. 左下に「WSL: Ubuntu-24.04」と出ていれば、WSL の中のファイルを編集できています

---

## E. Superpowers を入れる

Superpowers は Claude Code のプラグインで、「いきなりコードを書かず、要件の確認 → 計画 → テストを書く → 実装 → 確認」という手順を Claude に踏ませるスキル集です。この演習では、手法を作るときにこの流れを体験してもらいます。

### E-1. インストール

リポジトリのフォルダで `claude` を起動し、Claude Code の入力欄に次を入力します:

```
/plugin install superpowers@claude-plugins-official
```

うまくいかない場合は、作者のマーケットプレイス経由で入れます(2行を順に):

```
/plugin marketplace add obra/superpowers-marketplace
```

```
/plugin install superpowers@superpowers-marketplace
```

インストール後、`/exit` で一度終了し、`claude` を起動し直します。

> このリポジトリには `.claude/settings.json` で Superpowers を有効にする設定が入っています。
> フォルダを「信頼する」と答えると、未インストールの場合にインストールを促されることがあります。そのときは許可してください。

### E-2. 確認

1. `/plugin` と入力し、インストール済みの一覧に **superpowers** があること
2. 次のように話しかけてみる:

   ```
   ベースラインより良い復旧順序の手法を作りたい。まず方針を一緒に考えて。
   ```

   Claude がすぐにコードを書き始めず、**質問を返しながら設計を詰める**(brainstorming スキルが動く)なら成功です。

### E-3. 更新

`/plugin` のメニューからマーケットプレイスとプラグインを更新できます。授業期間中は、担当教員から指示があったときだけ更新してください(途中で挙動が変わるのを避けるため)。

### E-4. 補足

- Superpowers は、利用状況の匿名データ送信を `SUPERPOWERS_DISABLE_TELEMETRY=1` で止められます(Claude Code 自体の `DISABLE_TELEMETRY` にも従います)。学内ルールで外部送信を抑える必要がある場合は、`~/.bashrc` に次を追記してください:

  ```bash
  export SUPERPOWERS_DISABLE_TELEMETRY=1
  ```

- Claude Code を Windows と WSL の両方で使う場合、プラグインはそれぞれに入れる必要があります。

---

## チェックリスト(第1回までに)

- [ ] `wsl -l -v` で VERSION 2(Windows のみ)
- [ ] `uv --version` が表示される
- [ ] `claude` で配付アカウントにログインできる
- [ ] `python -m pytest` が `8 passed`
- [ ] `python scripts/run_baselines.py` でスコア表が出る
- [ ] `/plugin` に superpowers がある
