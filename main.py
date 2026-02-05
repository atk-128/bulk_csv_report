from __future__ import annotations

import argparse
import glob
import os
from dataclasses import dataclass

import pandas as pd
import matplotlib.pyplot as plt

import matplotlib as mpl

# 日本語フォント（MacならだいたいこれでOK）
for f in ["Hiragino Sans", "Hiragino Kaku Gothic ProN", "AppleGothic"]:
    try:
        mpl.rcParams["font.family"] = f
        break
    except Exception:
        pass

mpl.rcParams["axes.unicode_minus"] = False


REQUIRED_COLS = {"date", "product", "amount"}


def parse_args():
    p = argparse.ArgumentParser(description="複数CSVを一括集計してレポート出力（summary.csv + trend.png）")
    p.add_argument("--input-dir", default="data", help="入力CSVフォルダ（デフォルト: data）")
    p.add_argument("--output-dir", default="output", help="出力フォルダ（デフォルト: output）")
    p.add_argument("--pattern", default="*.csv", help="入力CSVのパターン（デフォルト: *.csv）")
    return p.parse_args()


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def list_csv_files(input_dir: str, pattern: str) -> list[str]:
    path = os.path.join(input_dir, pattern)
    files = sorted(glob.glob(path))
    return files


def read_one_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"{os.path.basename(path)} に必須列がありません: {sorted(missing)}")

    # 型を整える（壊れた行は落とす）
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    df = df.dropna(subset=["date", "amount"])
    return df[["date", "product", "amount"]]


def build_summary(all_df: pd.DataFrame) -> pd.DataFrame:
    # YYYY-MM で月を作る
    all_df = all_df.copy()
    all_df["month"] = all_df["date"].dt.to_period("M").astype(str)

    summary = (
        all_df.groupby("month", as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "total_amount"})
        .sort_values("month")
        .reset_index(drop=True)
    )
    return summary

def build_product_by_summary(all_df: pd.DataFrame) -> pd.DataFrame:
    """
    商品別の売上合計ランキングを作成
    """
    summary = (
        all_df.groupby("product", as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "total_amount"})
        .sort_values("total_amount", ascending=False)
        .reset_index(drop=True)
    )
    return summary


def export_summary_csv(summary: pd.DataFrame, output_dir: str):
    out_path = os.path.join(output_dir, "summary.csv")
    summary.to_csv(out_path, index=False)

def export_product_summary_csv(summary: pd.DataFrame, output_dir: str):
    out_path = os.path.join(output_dir, "summary_by_product.csv")
    summary.to_csv(out_path, index=False)


def export_trend_png(summary: pd.DataFrame, output_dir: str):
    if summary.empty:
        raise ValueError("集計結果が空なのでグラフを作れません（入力CSVを確認してください）")

    plt.figure(figsize=(10, 5))
    plt.plot(summary["month"], summary["total_amount"], marker="o")
    plt.title("Sales Trend (Monthly Total)")
    plt.xlabel("Month")
    plt.ylabel("Total Amount")
    plt.xticks(rotation=30)
    plt.tight_layout()

    out_path = os.path.join(output_dir, "sales_trend.png")
    plt.savefig(out_path, dpi=200)
    plt.close()

def export_product_top10_png(summary_by_product: pd.DataFrame, output_dir: str):
    """
    商品別合計（summary_by_product.csv）から Top10 を横棒グラフで出力
    """
    if summary_by_product.empty:
        raise ValueError("商品別集計が空なので Top10 グラフを作れません")

    top10 = (
        summary_by_product.sort_values("total_amount", ascending=False)
        .head(10)
        .copy()
    )

    # 横棒は「下が最大」になりがちなので、見やすく昇順にして下→上で伸ばす
    top10 = top10.sort_values("total_amount", ascending=True)

    plt.figure(figsize=(10, 6))
    plt.barh(top10["product"], top10["total_amount"])
    plt.title("Top 10 Products (Total Amount)")
    plt.xlabel("Total Amount")
    plt.ylabel("Product")
    plt.tight_layout()

    out_path = os.path.join(output_dir, "product_top10.png")
    plt.savefig(out_path, dpi=200)
    plt.close()

def main():
    args = parse_args()
    ensure_dir(args.output_dir)

    files = list_csv_files(args.input_dir, args.pattern)
    if not files:
        raise FileNotFoundError(f"入力CSVが見つかりません: {args.input_dir}/{args.pattern}")

    dfs: list[pd.DataFrame] = []
    for f in files:
        df = read_one_csv(f)
        dfs.append(df)
        print(f"✅ read: {f} ({len(df)} rows)")

    all_df = pd.concat(dfs, ignore_index=True)

    summary = build_summary(all_df)
    summary_by_product = build_product_by_summary(all_df)

    export_summary_csv(summary, args.output_dir)
    export_product_summary_csv(summary_by_product, args.output_dir)
    export_trend_png(summary, args.output_dir)
    export_product_top10_png(summary_by_product, args.output_dir)

    print("✅ 完了")
    print("出力先:", args.output_dir)
    print(" - summary.csv")
    print(" - sales_trend.png")
    print(" - summary_by_product.csv")
    print(" - product_top10.png")

if __name__ == "__main__":
    main()