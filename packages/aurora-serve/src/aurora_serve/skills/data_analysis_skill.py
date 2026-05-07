import json
from pathlib import Path
from typing import Any, Optional

from aurora_core.agent.skill.base import BaseSkill


class DataAnalysisSkill(BaseSkill):
    """Analyze a CSV/Excel/TSV file and return comprehensive statistics and insights."""

    @property
    def name(self) -> str:
        return "data_analysis"

    @property
    def description(self) -> str:
        return (
            "Perform comprehensive data analysis on a CSV, Excel, or TSV file. "
            "Returns overview statistics, numeric summaries, correlations, "
            "categorical breakdowns, time series detection, outlier counts, and top/bottom rankings."
        )

    @property
    def description_cn(self) -> str:
        return "对CSV/Excel/TSV文件执行全面数据分析，返回统计摘要、相关性、异常值和排名等。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the CSV, Excel (.xlsx), or TSV file to analyze.",
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, file_path: str = "", **kwargs: Any) -> str:
        if not file_path:
            return "No file_path provided."
        if not Path(file_path).exists():
            return f"File not found: {file_path}"

        try:
            import numpy as np
            import pandas as pd
        except ImportError as e:
            return f"Required libraries not available: {e}"

        ext = Path(file_path).suffix.lower()
        try:
            if ext in (".xls", ".xlsx"):
                df = pd.read_excel(file_path, engine="openpyxl", keep_default_na=False)
            elif ext == ".tsv":
                df = pd.read_csv(file_path, sep="\t", keep_default_na=False)
            elif ext == ".csv":
                df = pd.read_csv(file_path, keep_default_na=False)
            else:
                return f"Unsupported file format: {ext}. Supported: .csv, .xlsx, .xls, .tsv"
        except Exception as e:
            return f"Failed to read file: {e}"

        if df.empty:
            return "The file contains no data."

        # Convert empty strings to None/NaN for analysis
        df = df.replace({"": None})

        total_cells = int(df.shape[0] * df.shape[1])
        missing_cells = int(df.isnull().sum().sum())
        missing_pct = round((missing_cells / total_cells) * 100, 2) if total_cells > 0 else 0.0
        duplicate_rows = int(df.duplicated().sum())

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()

        # Try to detect datetime columns stored as strings
        for col in categorical_cols.copy():
            try:
                sample = df[col].dropna().head(100)
                if len(sample) > 0:
                    pd.to_datetime(sample)
                    datetime_cols.append(col)
                    categorical_cols.remove(col)
            except Exception:
                pass

        # Overview
        overview = {
            "rows": int(df.shape[0]),
            "cols": int(df.shape[1]),
            "missing_cells": missing_cells,
            "missing_pct": missing_pct,
            "duplicate_rows": duplicate_rows,
            "numeric_cols": numeric_cols,
            "categorical_cols": categorical_cols,
            "datetime_cols": datetime_cols,
        }

        # Numeric summaries
        numeric_summary = {}
        for col in numeric_cols[:10]:
            s = df[col].dropna()
            if len(s) > 0:
                mean_val = float(s.mean())
                std_val = float(s.std())
                cv = round(abs(std_val / mean_val) * 100, 1) if mean_val != 0 else 0.0
                numeric_summary[col] = {
                    "min": round(float(s.min()), 4),
                    "max": round(float(s.max()), 4),
                    "mean": round(mean_val, 4),
                    "median": round(float(s.median()), 4),
                    "std": round(std_val, 4),
                    "q25": round(float(s.quantile(0.25)), 4),
                    "q75": round(float(s.quantile(0.75)), 4),
                    "cv": cv,
                }

        # Correlations
        correlations = {}
        if len(numeric_cols) > 1:
            corr_df = df[numeric_cols].corr(method="pearson").fillna(0).round(2)
            strong_corrs = []
            for i, col1 in enumerate(numeric_cols):
                for j, col2 in enumerate(numeric_cols):
                    if i < j:
                        val = float(corr_df.iloc[i, j])
                        if abs(val) >= 0.5:
                            strong_corrs.append(f"{col1} vs {col2}: {val}")
            correlations["strong_correlations"] = strong_corrs

        # Categorical summaries
        categorical_summary = {}
        for col in categorical_cols[:6]:
            vc = df[col].value_counts().head(10)
            if len(vc) > 0:
                total_non_null = int(df[col].notna().sum())
                categorical_summary[col] = {
                    "unique_values": int(df[col].nunique()),
                    "top_value": str(vc.index[0]),
                    "top_count": int(vc.values[0]),
                    "top_share_pct": round((int(vc.values[0]) / total_non_null) * 100, 1) if total_non_null > 0 else 0.0,
                    "value_counts": {str(k): int(v) for k, v in vc.items()},
                }

        # Time series detection
        time_series = {}
        if datetime_cols and numeric_cols:
            date_col = datetime_cols[0]
            try:
                df_ts = df.copy()
                df_ts[date_col] = pd.to_datetime(df_ts[date_col], errors="coerce")
                df_ts = df_ts.dropna(subset=[date_col])
                num_col = numeric_cols[0]
                df_ts = df_ts.dropna(subset=[num_col])
                if not df_ts.empty:
                    df_ts = df_ts.set_index(date_col)
                    monthly = df_ts[num_col].resample("M").mean().dropna()
                    if len(monthly) < 3:
                        monthly = df_ts[num_col].resample("D").mean().dropna()
                    monthly = monthly.tail(100)
                    if len(monthly) >= 2:
                        time_series = {
                            "date_col": date_col,
                            "metric": num_col,
                            "points": int(len(monthly)),
                            "start": round(float(monthly.iloc[0]), 2),
                            "end": round(float(monthly.iloc[-1]), 2),
                            "change_pct": round(
                                ((float(monthly.iloc[-1]) - float(monthly.iloc[0])) / abs(float(monthly.iloc[0]))) * 100,
                                1,
                            )
                            if float(monthly.iloc[0]) != 0
                            else 0.0,
                        }
            except Exception:
                pass

        # Outliers (IQR method)
        outliers = {}
        for col in numeric_cols[:8]:
            s = df[col].dropna()
            if len(s) > 0:
                q1 = float(s.quantile(0.25))
                q3 = float(s.quantile(0.75))
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                n_outliers = int(((s < lower) | (s > upper)).sum())
                outliers[col] = {
                    "count": n_outliers,
                    "pct": round((n_outliers / len(s)) * 100, 1) if len(s) > 0 else 0.0,
                    "lower_bound": round(lower, 4),
                    "upper_bound": round(upper, 4),
                }

        # Top/Bottom 5
        top_bottom = {}
        if numeric_cols and len(df) > 0:
            rank_col = numeric_cols[0]
            label_col = categorical_cols[0] if categorical_cols else None
            df_sorted = df.dropna(subset=[rank_col]).sort_values(rank_col, ascending=False)
            top5 = df_sorted.head(5)
            bottom5 = df_sorted.tail(5).iloc[::-1]

            def extract_ranked(subset):
                labels = []
                values = []
                for _, row in subset.iterrows():
                    lbl = str(row[label_col])[:30] if label_col else str(row.name)
                    labels.append(lbl)
                    values.append(round(float(row[rank_col]), 2))
                return {"labels": labels, "values": values}

            top_bottom = {
                "rank_col": rank_col,
                "top5": extract_ranked(top5),
                "bottom5": extract_ranked(bottom5),
            }

        result = {
            "overview": overview,
            "numeric_summary": numeric_summary,
            "correlations": correlations,
            "categorical_summary": categorical_summary,
            "time_series": time_series,
            "outliers": outliers,
            "top_bottom": top_bottom,
        }

        # Build text summary
        lines = [
            f"Data Analysis Report for {Path(file_path).name}",
            "=" * 50,
            f"Rows: {overview['rows']}, Columns: {overview['cols']}",
            f"Missing cells: {overview['missing_cells']} ({overview['missing_pct']}%)",
            f"Duplicate rows: {overview['duplicate_rows']}",
            f"Numeric columns: {len(numeric_cols)}",
            f"Categorical columns: {len(categorical_cols)}",
            f"Datetime columns: {len(datetime_cols)}",
            "",
            "Numeric Summaries:",
        ]
        for col, stats in numeric_summary.items():
            lines.append(
                f"- {col}: min={stats['min']}, max={stats['max']}, "
                f"mean={stats['mean']}, median={stats['median']}, std={stats['std']}, CV={stats['cv']}%"
            )

        if correlations.get("strong_correlations"):
            lines.extend(["", "Strong Correlations (|r| >= 0.5):"])
            for c in correlations["strong_correlations"]:
                lines.append(f"- {c}")

        if categorical_summary:
            lines.extend(["", "Categorical Summaries:"])
            for col, stats in categorical_summary.items():
                lines.append(
                    f"- {col}: {stats['unique_values']} unique values, "
                    f"most common='{stats['top_value']}' ({stats['top_count']} occurrences, {stats['top_share_pct']}%)"
                )

        if time_series:
            lines.extend(["", "Time Series Detection:"])
            lines.append(
                f"- Detected time column '{time_series['date_col']}' with metric '{time_series['metric']}'"
            )
            lines.append(
                f"  Points: {time_series['points']}, Start: {time_series['start']}, End: {time_series['end']}, Change: {time_series['change_pct']}%"
            )

        if outliers:
            lines.extend(["", "Outlier Summary (IQR method):"])
            for col, info in outliers.items():
                if info["count"] > 0:
                    lines.append(
                        f"- {col}: {info['count']} outliers ({info['pct']}%), bounds=[{info['lower_bound']}, {info['upper_bound']}]"
                    )

        if top_bottom:
            lines.extend(["", f"Top/Bottom 5 by {top_bottom['rank_col']}:"])
            lines.append(f"- Top 5: {list(zip(top_bottom['top5']['labels'], top_bottom['top5']['values']))}")
            lines.append(f"- Bottom 5: {list(zip(top_bottom['bottom5']['labels'], top_bottom['bottom5']['values']))}")

        lines.extend(["", "Raw JSON result:", json.dumps(result, ensure_ascii=False, indent=2)])
        return "\n".join(lines)
