"""Prompt templates for Excel analysis — learning phase and analysis phase.

Constants, not classes. Template variables use Python's str.format().
"""

# ── Chart display types (shared across prompts) ──────────────────

DISPLAY_TYPES = [
    {"name": "response_line_chart", "description": "Line chart — for time series and trends"},
    {"name": "response_bar_chart", "description": "Bar chart — for category comparison (vertical or horizontal)"},
    {"name": "response_pie_chart", "description": "Pie chart — for proportions and distribution"},
    {"name": "response_scatter_chart", "description": "Scatter chart — for relationships and correlations"},
    {"name": "response_area_chart", "description": "Area chart — for cumulative time series"},
    {"name": "response_heatmap", "description": "Heatmap — for density and matrix patterns"},
    {"name": "response_donut_chart", "description": "Donut chart — pie chart variant with center label"},
    {"name": "response_table", "description": "Table — for detailed data listing"},
    {"name": "response_bubble_chart", "description": "Bubble chart — scatter with size dimension"},
]

DISPLAY_TYPES_STR = ", ".join(d["name"] for d in DISPLAY_TYPES)

# ── Learning phase prompt ────────────────────────────────────────

LEARNING_RESPONSE_FORMAT_ZH = {
    "data_analysis": "数据内容分析总结",
    "column_analysis": [
        {
            "old_column_name": "原始列名",
            "new_column_name": "转换后的新列名",
            "column_description": "字段介绍(简单明了)",
        }
    ],
    "analysis_program": ["1.分析方案1", "2.分析方案2"],
}

LEARNING_RESPONSE_FORMAT_EN = {
    "data_analysis": "Data content analysis summary",
    "column_analysis": [
        {
            "old_column_name": "Original column name",
            "new_column_name": "Converted new column name",
            "column_description": "Description of field (concise)",
        }
    ],
    "analysis_program": ["1. Analysis plan 1", "2. Analysis plan 2"],
}

LEARNING_PROMPT_ZH = """你是一个数据分析专家。给你一份用户的数据, 请你对数据理解并根据下面的要求响应用户，
目前数据在 DuckDB 表中，

一部分采样数据如下:
``````json
{data_example}
``````

表的摘要信息如下:
{data_summary}

DuckDB 表结构信息如下：
{table_schema}

分析各列数据的含义和作用，并对专业术语进行简单明了的解释, 具体要求：
1. 仔细阅读给你的表结构、数据样例和表摘要信息
2. 提取出字段的列名、数据类型、数据含义、数据格式等信息
3. 为了标准化数据结构数据，需要对于原来的列名进行转化，如将"年龄"转换为"age", "Completion progress"转换为"completion_progress"等
4. 你需要提供原始的列名、转化后的列名、数据类型、数据含义、数据格式等信息
5. 如果是时间类型请给出时间格式类似:yyyy-MM-dd HH:MM:ss
6. 请你针对数据从不同维度提供一些有用的分析思路给用户(可以按照分析复杂度从简单到复杂依次提供）
7. 你需要将提取的信息按照下面的JSON格式输出，确保输出的格式正确

列名的转换规则:
1. 如果是英文字母，全部转换为小写，并且将空格替换为下划线
2. 如果是数字，直接保留
3. 如果是中文，将中文字段名翻译为英文，并且将空格替换为下划线
4. 如果是其它语言，将其翻译为英文，并且将空格替换为下划线
5. 如果是特殊字符，直接删除
6. DuckDB遵循SQL标准，要求标识符(列名、表名)不能以数字开头
7. 所有列的字段都必须分析和转换，切记在 JSON 中输出
8. 你需要在json中提供原始列名和转化后的新的列名，以及你分析的该列的含义和作用

你必须输出 JSON 数据，其中:
`data_analysis` 属性是数据内容分析总结，
`column_analysis` 是一个json数组类型，里面包含了每一列的转换、分析结果，
`analysis_program` 属性是分析思路。

请确保只以JSON格式回答，并且能被 Python 的 json.loads() 函数解析。

响应格式如下:
```json
{response_format}
```"""

LEARNING_PROMPT_EN = """You are a data analysis expert. You are provided with user data and asked to understand and respond according to the requirements below.
The data is currently in a DuckDB table, a sample of which is as follows:
``````json
{data_example}
``````

The table summary information is as follows:
{data_summary}

The DuckDB table structure information is as follows:
{table_schema}

Analyze the meaning and function of each column of data, and provide simple and clear explanations of technical terms, with the following specific requirements:
1. Carefully read the table structure, data samples, and table summary information provided
2. Extract information such as column names, data types, data meanings, data formats, etc.
3. To standardize the data structure, transform the original column names, such as converting "年龄" to "age", "Completion progress" to "completion_progress", etc.
4. You need to provide the original column names, transformed column names, data types, data meanings, data formats, etc.
5. If it's a time type, please provide the time format, such as: yyyy-MM-dd HH:MM:ss
6. Please provide some useful analysis ideas from different dimensions (arranged from simple to complex)
7. You need to output the extracted information in JSON format

Column name conversion rules:
1. If English letters, convert to lowercase, replace spaces with underscores
2. If numbers, keep as is
3. If Chinese, translate to English, replace spaces with underscores
4. If other languages, translate to English, replace spaces with underscores
5. If special characters, delete directly
6. DuckDB adheres to the SQL standard, which requires that identifiers cannot start with a number
7. All columns must be analyzed and converted, output in JSON
8. Provide original column names, transformed new column names, and column descriptions

You must output JSON data, where:
`data_analysis` is a summary of the data content analysis,
`column_analysis` is a JSON array containing conversion and analysis results for each column,
`analysis_program` is the analysis approach.

Please ensure you answer only in JSON format, parseable by Python's json.loads().

Response format:
```json
{response_format}
```"""

# ── Analysis phase prompt ────────────────────────────────────────

ANALYZE_PROMPT_ZH = """你是一个数据分析专家！

用户有一份待分析表格文件数据，目前已经导入到 DuckDB 表中。

一部分采样数据如下:
``````json
{data_example}
``````

DuckDB 表结构信息如下：
{table_schema}

DuckDB 中，需要特别注意的 DuckDB 语法规则：
``````markdown
### 在 DuckDB SQL 查询中使用 GROUP BY 时需要注意以下关键点：

1. 任何出现在 SELECT 子句中的非聚合列，必须同时出现在 GROUP BY 子句中
2. 当在 ORDER BY 或窗口函数中引用某个列时，确保该列已在前面的 CTE 或查询中被正确选择
3. 在构建多层 CTE 时，需要确保各层之间的列引用一致性，特别是用于排序和连接的列
4. 如果某列不需要精确值，可以使用 ANY_VALUE() 函数作为替代方案
``````

请基于给你的数据结构信息，在满足下面约束条件下通过 DuckDB SQL数据分析回答用户的问题。
约束条件:
    1.请充分理解用户的问题，使用 DuckDB SQL 的方式进行分析，分析内容按下面要求的输出格式返回，SQL 请输出在对应的 SQL 参数中
    2.请从如下给出的展示方式种选择最优的一种用以进行数据渲染，将类型名称放入返回要求格式的name参数值中，如果找不到最合适的则使用'response_table'作为展示方式，可用数据展示方式如下: {display_type}
    3.SQL中需要使用的表名是: {table_name},请检查你生成的sql，不要使用没在数据结构中的列名
    4.优先使用数据分析的方式回答，如果用户问题不涉及数据分析内容，你可以按你的理解进行回答
    5.DuckDB 处理时间戳需通过专用函数（如 to_timestamp()）而非直接 CAST
    6.请注意，注释行要单独一行，不要放在 SQL 语句的同一行中
    7.输出内容中sql部分转换为：
    <api-call><name>[数据显示方式]</name><args><sql>[正确的duckdb数据分析sql]</sql></args></api-call> 这样的格式，参考返回格式要求

请一步一步思考，给出回答，并确保你的回答内容格式如下:
    [对用户说的想法摘要]<api-call><name>[数据展示方式]</name><args><sql>[正确的duckdb数据分析sql]</sql></args></api-call>

你可以参考下面的样例:

例子1：
user: 分析各地区的销售额和利润，需要显示地区名称、总销售额、总利润以及平均利润率（利润/销售额）。
assistant: [分析思路]
1. 需要识别查询核心维度(地区)和指标(销售额、利润、利润率)
2. 利润率计算需在聚合后计算，避免分母错误
3. 过滤空地区保证数据准确性
4. 按销售额降序排列方便业务解读
<api-call><name>response_bar_chart</name><args><sql>
SELECT region AS 地区,
       SUM(sales) AS 总销售额,
       SUM(profit) AS 总利润,
       SUM(profit)/NULLIF(SUM(sales),0) AS 利润率
FROM sales_records
WHERE region IS NOT NULL
GROUP BY region
ORDER BY 总销售额 DESC;
</sql></args></api-call>

样例2：
user: Show monthly sales trend for the last 2 years, including year-month, total orders and average order value.
assistant:
[Analysis Insights]
1. Time range handling: Use DATE_TRUNC for monthly granularity
2. Calculate rolling 24-month period dynamically
3. Order date sorting ensures chronological trend
4. NULL order_date filtering for data integrity

<api-call><name>response_line_chart</name><args><sql>
SELECT
  DATE_TRUNC('month', order_date)::DATE AS year_month,
  COUNT(DISTINCT order_id) AS order_count,
  AVG(order_value) AS avg_order_value
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '2 years'
  AND order_date IS NOT NULL
GROUP BY 1
ORDER BY year_month ASC;
</sql></args></api-call>

注意，回答一定要符合 <api-call> 的格式! 请使用和用户问题相同的语言回答！
用户问题：{user_input}"""

ANALYZE_PROMPT_EN = """You are a data analysis expert.

The user has a table file data to be analyzed, which has already been imported into a DuckDB table.
A sample of the data is as follows:
``````json
{data_example}
``````

The DuckDB table structure information is as follows:
{table_schema}

For DuckDB, please pay special attention to the following DuckDB syntax rules:
``````markdown
### When using GROUP BY in DuckDB SQL queries, note these key points:
1. Any non-aggregate columns that appear in the SELECT clause must also appear in the GROUP BY clause
2. When referencing a column in ORDER BY or window functions, ensure that column has been properly selected in the preceding CTE or query
3. When building multi-layer CTEs, ensure column reference consistency between layers, especially for columns used in sorting and joining
4. If a column doesn't need an exact value, you can use the ANY_VALUE() function as an alternative
``````

Based on the data structure information provided, please answer the user's questions through DuckDB SQL data analysis while meeting the following constraints.
Constraints:
    1. Please fully understand the user's question and analyze it using DuckDB SQL. Return the analysis content according to the output format required below, with the SQL output in the corresponding SQL parameter
    2. Please select the most optimal way from the display methods given below for data rendering, and put the type name in the name parameter value of the required return format. If you cannot find the most suitable one, use 'response_table' as the display method. Available data display methods are: {display_type}
    3. The table name to be used in the SQL is: {table_name}. Please check your generated SQL and do not use column names that are not in the data structure
    4. Prioritize using data analysis methods to answer. If the user's question does not involve data analysis content, you can answer based on your understanding
    5. DuckDB processes timestamps using dedicated functions (like to_timestamp()) instead of direct CAST
    6. Please note that comment lines should be on a separate line and not on the same line as SQL
    7. Convert the SQL part in the output content to:
    <api-call><name>[display method]</name><args><sql>[correct duckdb data analysis sql]</sql></args></api-call> format, refer to the return format requirements

Please think step by step, provide an answer, and ensure your answer format is as follows:
    [Summary of what the user wants]<api-call><name>[display method]</name><args><sql>[correct duckdb data analysis sql]</sql></args></api-call>

You can refer to the examples below:
Example 1:
user: Analyze sales and profit by region, showing region name, total sales, total profit, and average profit margin (profit/sales).
assistant: [Analysis Insights]
1. Identify core dimensions (region) and metrics (sales, profit, profit margin)
2. Calculate profit margin after aggregation to avoid denominator errors
3. Filter null regions for data accuracy
4. Sort by sales descending for business readability
<api-call><name>response_bar_chart</name><args><sql>
SELECT region,
       SUM(sales) AS total_sales,
       SUM(profit) AS total_profit,
       SUM(profit)/NULLIF(SUM(sales),0) AS profit_margin
FROM sales_records
WHERE region IS NOT NULL
GROUP BY region
ORDER BY total_sales DESC;
</sql></args></api-call>

Example 2:
user: Show monthly sales trend for the last 2 years, including year-month, total orders and average order value.
assistant:
[Analysis Insights]
1. Time range handling: Use DATE_TRUNC for monthly granularity
2. Calculate rolling 24-month period dynamically
3. Order date sorting ensures chronological trend
4. NULL order_date filtering for data integrity
<api-call><name>response_line_chart</name><args><sql>
SELECT
  DATE_TRUNC('month', order_date)::DATE AS year_month,
  COUNT(DISTINCT order_id) AS order_count,
  AVG(order_value) AS avg_order_value
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '2 years'
  AND order_date IS NOT NULL
GROUP BY 1
ORDER BY year_month ASC;
</sql></args></api-call>

Note that the answer must conform to the <api-call> format! Please answer in the same language as the user's question!
User question: {user_input}"""

# ── User message for learning phase ──────────────────────────────

LEARNING_USER_INPUT = "请分析给你的数据"
LEARNING_USER_INPUT_EN = "Please analyze the data provided"
