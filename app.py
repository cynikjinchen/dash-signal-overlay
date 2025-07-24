#信号叠加显示，变化率及信号均移动平均

# 导入需要的库
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from dash.dependencies import ALL

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 读取数据文件
df = pd.read_excel("brokerSignal.xlsx")

# ========== 数据预处理 ==========
df['日期'] = pd.to_datetime(df['日期'])
df['年份'] = df['日期'].dt.year

# 提取指标列
indicator_cols = [
    '中国大豆压榨企业原料大豆库存', '大豆港口库存', '大豆现货压榨利润', '大豆压榨盘面利润',
    '豆粕基差', '豆粕仓单', '豆粕库存', '豆菜价差', '生猪存栏', '日内动量', '双均线', 
    '中值双均线', '考夫曼均线', '顺势指标CCI', 'TRIX指标', '布林带', '波动趋势', '佳庆指标'
]

# 去除关键字段缺失值
df = df.dropna(subset=['持仓量', '变化率', '价格'])

# 合约名称排序
contract_order = df.groupby('合约名称')['日期'].min().sort_values().index.tolist()
df['合约名称'] = pd.Categorical(df['合约名称'], categories=contract_order, ordered=True)

# 转换多/空头和加/减仓编码为文字标签
df['多空标签'] = df['多/空头'].map({'l': '多头', 's': '空头'})
df['仓位动作标签'] = df['加/减仓'].map({1: '加仓', -1: '减仓', 0: '不变'})

# ========= 指标分组 =========
fundamental_signals = [
    "中国大豆压榨企业原料大豆库存", "大豆港口库存", "大豆现货压榨利润", "大豆压榨盘面利润",
    "豆粕基差", "豆粕仓单", "豆粕库存", "豆菜价差", "生猪存栏"
]
trend_indicators = ["双均线", "中值双均线", "考夫曼均线", "TRIX指标"]
oscillators = ["顺势指标CCI", "布林带", "日内动量"]
volume_indicators = ["佳庆指标", "波动趋势"]

# ========== 初始化 Dash App ==========
app = Dash(__name__)
server = app.server  # 这行加在`app = Dash(__name__)`之后
# ========== 工具函数 ==========
def add_reference_lines(fig, dff, show_ref, yaxis_id='y3'):
    def normalize(series):
        if series.max() == series.min():
            return series * 0  # 避免除零
        return (series - series.min()) / (series.max() - series.min())
    if 'holding' in show_ref:
        fig.add_trace(go.Scatter(
            x=dff['日期'],
            y=normalize(dff['持仓量']),
            name='持仓量参考',
            line=dict(color='blue', dash='dot', width=3),
            opacity=1,
            yaxis=yaxis_id
        ))
    if 'price' in show_ref:
        fig.add_trace(go.Scatter(
            x=dff['日期'],
            y=normalize(dff['价格']),
            name='价格参考',
            line=dict(color='red', dash='dot', width=3),
            opacity=1,
            yaxis=yaxis_id
        ))
    return fig

# 应用布局设计
app.layout = html.Div([
    html.H2("豆粕持仓数据分析系统", style={"textAlign": "center"}),
    
    # 筛选控件
    html.Div([
        html.Div([
            html.Label("选择经纪商:", style={'font-weight': 'bold'}),
            dcc.Dropdown(
                id='broker-dropdown',
                options=[{'label': name, 'value': name} for name in df['经纪商名称'].unique()],
                multi=True,
                placeholder='请选择经纪商...',
                style={'width': '100%'}
            )
        ], style={'width': '24%', 'display': 'inline-block', 'padding': '0 10px'}),
        
        html.Div([
            html.Label("选择年份:", style={'font-weight': 'bold'}),
            dcc.Dropdown(
                id='year-dropdown',
                options=[{'label': str(y), 'value': y} for y in sorted(df['年份'].unique())],
                multi=True,
                placeholder='请选择年份...',
                style={'width': '100%'}
            )
        ], style={'width': '15%', 'display': 'inline-block', 'padding': '0 10px'}),
        
        html.Div([
            html.Label("选择多/空头:", style={'font-weight': 'bold'}),
            dcc.Dropdown(
                id='long-short-dropdown',
                options=[{'label': '多头', 'value': 'l'}, {'label': '空头', 'value': 's'}],
                placeholder='请选择多/空头...',
                multi=True,
                style={'width': '100%'}
            )
        ], style={'width': '15%', 'display': 'inline-block', 'padding': '0 10px'}),
        
        html.Div([
            html.Label("选择加/减仓:", style={'font-weight': 'bold'}),
            dcc.Dropdown(
                id='action-dropdown',
                options=[{'label': '加仓', 'value': 1}, {'label': '减仓', 'value': -1}, {'label': '不变', 'value': 0}],
                placeholder='请选择加/减仓...',
                multi=True,
                style={'width': '100%'}
            )
        ], style={'width': '15%', 'display': 'inline-block', 'padding': '0 10px'}),
        
        html.Div([
            html.Label("选择合约名称:", style={'font-weight': 'bold'}),
            dcc.Dropdown(
                id='contract-dropdown',
                placeholder='请选择合约...',
                style={'width': '100%'}
            )
        ], style={'width': '24%', 'display': 'inline-block', 'padding': '0 10px'})
    ], style={'margin': '10px 0', 'display': 'flex', 'justify-content': 'space-between'}),

    html.Hr(),

    # 平滑窗口滑块
    html.Div([
        html.Label("平滑窗口(天):", style={'font-weight': 'bold', 'margin-right': '10px'}),
        dcc.Slider(
            id='smoothing-window',
            min=1,
            max=30,
            step=1,
            value=7,
            marks={i: str(i) for i in [1, 5, 10, 15, 20, 25, 30]},
            tooltip={'placement': 'bottom', 'always_visible': True}
        )
    ], style={'margin': '20px 0'}),

    html.Hr(),

    # 主图一：价格/持仓量
    html.Div([
        html.Label("主图1显示选项:", style={'font-weight': 'bold'}),
        dcc.Checklist(
            id='main-abs-control',
            options=[
                {'label': '持仓量 (左轴)', 'value': 'holding'},
                {'label': '价格 (右轴)', 'value': 'price'}
            ],
            value=['holding', 'price'],
            inline=True
        ),
        dcc.Graph(id='main-chart-absolute')
    ]),

    html.Hr(),

    # 主图二：变化率
    html.Div([
        html.Label("主图2显示选项:", style={'font-weight': 'bold'}),
        dcc.Checklist(
            id='main-change-control',
            options=[
                {'label': '持仓变化率 (左轴)', 'value': 'holding_change'},
                {'label': '价格变化率 (右轴)', 'value': 'price_change'}
            ],
            value=['holding_change', 'price_change'],
            inline=True
        ),
        dcc.Graph(id='main-chart-change')
    ]),

    html.Hr(),

    # 基本面信号图表
    html.Div([
        html.H4("基本面信号", style={'margin-bottom': '10px'}),
        html.Div([
            dcc.Checklist(
                id='fundamental-control',
                options=[{'label': sig, 'value': sig} for sig in fundamental_signals],
                value=fundamental_signals[:9],
                inline=True,
                style={'margin-right': '20px'}
            ),
            dcc.Checklist(
                id='fundamental-avg-control',
                options=[{'label': '显示平均值', 'value': 'show_avg'}],
                value=[],
                inline=True
            ),
            dcc.Checklist(
                id='fundamental-ref-control',
                options=[
                    {'label': '持仓量参考', 'value': 'holding'},
                    {'label': '价格参考', 'value': 'price'}
                ],
                value=[],
                inline=True,
                style={'margin-left': '20px'}
            )
        ], style={'margin-bottom': '15px'}),
        dcc.Graph(id='fundamental-chart')
    ], style={'padding': '10px', 'border': '1px solid #eee', 'border-radius': '5px'}),

    html.Hr(),

    # 趋势类指标图表
    html.Div([
        html.H4("趋势类指标", style={'margin-bottom': '10px'}),
        html.Div([
            dcc.Checklist(
                id='trend-control',
                options=[{'label': sig, 'value': sig} for sig in trend_indicators],
                value=trend_indicators[:4],
                inline=True,
                style={'margin-right': '20px'}
            ),
            dcc.Checklist(
                id='trend-avg-control',
                options=[{'label': '显示平均值', 'value': 'show_avg'}],
                value=[],
                inline=True
            ),
            dcc.Checklist(
                id='trend-ref-control',
                options=[
                    {'label': '持仓量参考', 'value': 'holding'},
                    {'label': '价格参考', 'value': 'price'}
                ],
                value=[],
                inline=True,
                style={'margin-left': '20px'}
            )
        ], style={'margin-bottom': '15px'}),
        dcc.Graph(id='trend-chart')
    ], style={'padding': '10px', 'border': '1px solid #eee', 'border-radius': '5px'}),

    html.Hr(),

    # 震荡类指标图表
    html.Div([
        html.H4("震荡类指标", style={'margin-bottom': '10px'}),
        html.Div([
            dcc.Checklist(
                id='oscillator-control',
                options=[{'label': sig, 'value': sig} for sig in oscillators],
                value=oscillators[:3],
                inline=True,
                style={'margin-right': '20px'}
            ),
            dcc.Checklist(
                id='oscillator-avg-control',
                options=[{'label': '显示平均值', 'value': 'show_avg'}],
                value=[],
                inline=True
            ),
            dcc.Checklist(
                id='oscillator-ref-control',
                options=[
                    {'label': '持仓量参考', 'value': 'holding'},
                    {'label': '价格参考', 'value': 'price'}
                ],
                value=[],
                inline=True,
                style={'margin-left': '20px'}
            )
        ], style={'margin-bottom': '15px'}),
        dcc.Graph(id='oscillator-chart')
    ], style={'padding': '10px', 'border': '1px solid #eee', 'border-radius': '5px'}),

        # ======== 量能类指标图表 ========
    html.Div([
        html.H4("量能类指标", style={'margin-bottom': '10px'}),
        html.Div([
            dcc.Checklist(
                id='volume-control',
                options=[{'label': sig, 'value': sig} for sig in volume_indicators],
                value=volume_indicators,
                inline=True,
                style={'margin-right': '20px'}
            ),
            dcc.Checklist(
                id='volume-avg-control',
                options=[{'label': '显示平均值', 'value': 'show_avg'}],
                value=[],
                inline=True
            ),
            dcc.Checklist(
                id='volume-ref-control',
                options=[
                    {'label': '持仓量参考', 'value': 'holding'},
                    {'label': '价格参考', 'value': 'price'}
                ],
                value=[],
                inline=True,
                style={'margin-left': '20px'}
            )
        ], style={'margin-bottom': '15px'}),
        dcc.Graph(id='volume-chart')
    ], style={'padding': '10px', 'border': '1px solid #eee', 'border-radius': '5px'}),


    html.Hr(),
    dcc.Graph(id='heatmap-all')

    # html.Hr(),
    # html.H3("SHAP信号对加/减仓的解释强度"),
    # dcc.Graph(id='shap-action-heatmap')
])

# ========== 回调函数 ==========

# 更新合约名称下拉选项
@app.callback(
    Output('contract-dropdown', 'options'),
    [Input('broker-dropdown', 'value'),
     Input('year-dropdown', 'value'),
     Input('long-short-dropdown', 'value'),
     Input('action-dropdown', 'value')]
)
def update_contract_dropdown(selected_brokers, selected_year, selected_long_short, selected_action):
    if not selected_brokers or not selected_year:
        return []
    if isinstance(selected_year, int):
        selected_year = [selected_year]
    filtered_df = df[
        (df['经纪商名称'].isin(selected_brokers)) &
        (df['年份'].isin(selected_year))
    ]
    if selected_long_short:
        filtered_df = filtered_df[filtered_df['多/空头'].isin(selected_long_short)]
    if selected_action:
        filtered_df = filtered_df[filtered_df['加/减仓'].isin(selected_action)]
    contracts = filtered_df['合约名称'].dropna().unique().tolist()
    contracts_sorted = [c for c in contract_order if c in contracts]
    return [{'label': c, 'value': c} for c in contracts_sorted]

# 移除原 main-chart 回调，新增如下两个回调：

@app.callback(
    Output('main-chart-absolute', 'figure'),
    [Input('broker-dropdown', 'value'),
     Input('year-dropdown', 'value'),
     Input('long-short-dropdown', 'value'),
     Input('action-dropdown', 'value'),
     Input('contract-dropdown', 'value'),
     Input('main-abs-control', 'value'),
     Input('smoothing-window', 'value')]
)
def update_main_chart_absolute(selected_brokers, selected_year, selected_long_short, selected_action,
                              selected_contract, display_options, window_size):
    if not selected_brokers or not selected_year or not selected_contract:
        return go.Figure()
    if isinstance(selected_year, int):
        selected_year = [selected_year]
    if isinstance(selected_contract, str):
        selected_contract = [selected_contract]
    dff = df[(df['经纪商名称'].isin(selected_brokers)) &
             (df['年份'].isin(selected_year)) &
             (df['合约名称'].isin(selected_contract))].copy()
    if selected_long_short:
        dff = dff[dff['多/空头'].isin(selected_long_short)]
    if selected_action:
        dff = dff[dff['加/减仓'].isin(selected_action)]
    fig = go.Figure()
    if 'holding' in display_options:
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=dff['持仓量'],
            mode='lines',
            name='持仓量',
            line=dict(color='blue'),
            yaxis='y'
        ))
    if 'price' in display_options:
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=dff['价格'],
            mode='lines',
            name='价格',
            line=dict(color='red'),
            yaxis='y2'
        ))
    fig.update_layout(
        yaxis=dict(title='持仓量', side='left'),
        yaxis2=dict(title='价格', side='right', overlaying='y'),
        xaxis=dict(title='日期'),
        title='价格/持仓量',
        hovermode='x unified',
        height=400,
        margin=dict(l=60, r=60, t=60, b=60)
    )
    return fig

@app.callback(
    Output('main-chart-change', 'figure'),
    [Input('broker-dropdown', 'value'),
     Input('year-dropdown', 'value'),
     Input('long-short-dropdown', 'value'),
     Input('action-dropdown', 'value'),
     Input('contract-dropdown', 'value'),
     Input('main-change-control', 'value'),
     Input('smoothing-window', 'value')]
)
def update_main_chart_change(selected_brokers, selected_year, selected_long_short, selected_action,
                            selected_contract, display_options, window_size):
    if not selected_brokers or not selected_year or not selected_contract:
        return go.Figure()
    if isinstance(selected_year, int):
        selected_year = [selected_year]
    if isinstance(selected_contract, str):
        selected_contract = [selected_contract]
    dff = df[(df['经纪商名称'].isin(selected_brokers)) &
             (df['年份'].isin(selected_year)) &
             (df['合约名称'].isin(selected_contract))].copy()
    if selected_long_short:
        dff = dff[dff['多/空头'].isin(selected_long_short)]
    if selected_action:
        dff = dff[dff['加/减仓'].isin(selected_action)]
    dff['平滑变化率'] = dff['变化率'].rolling(window=window_size, min_periods=1).mean()
    dff['平滑价格变化率'] = dff['价格变化率'].rolling(window=window_size, min_periods=1).mean()
    fig = go.Figure()
    if 'holding_change' in display_options:
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=dff['平滑变化率'],
            mode='lines',
            name='持仓变化率',
            line=dict(color='green'),
            yaxis='y'
        ))
    if 'price_change' in display_options:
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=dff['平滑价格变化率'],
            mode='lines',
            name='价格变化率',
            line=dict(color='purple'),
            yaxis='y2'
        ))
    fig.update_layout(
        yaxis=dict(title='持仓变化率', side='left', tickformat='.2%'),
        yaxis2=dict(title='价格变化率', side='right', overlaying='y', tickformat='.2%'),
        xaxis=dict(title='日期'),
        title='变化率',
        hovermode='x unified',
        height=400,
        margin=dict(l=60, r=60, t=60, b=60)
    )
    return fig

# 更新基本面信号图表
@app.callback(
    Output('fundamental-chart', 'figure'),
    [Input('broker-dropdown', 'value'),
     Input('year-dropdown', 'value'),
     Input('long-short-dropdown', 'value'),
     Input('action-dropdown', 'value'),
     Input('contract-dropdown', 'value'),
     Input('fundamental-control', 'value'),
     Input('fundamental-avg-control', 'value'),
     Input('fundamental-ref-control', 'value'),
     Input('smoothing-window', 'value')]
)
def update_fundamental_chart(selected_brokers, selected_year, selected_long_short, selected_action,
                            selected_contract, display_signals, show_avg, show_ref, window_size):
    if not selected_brokers or not selected_year or not selected_contract or not display_signals:
        return go.Figure()
    if isinstance(selected_year, int):
        selected_year = [selected_year]
    if isinstance(selected_contract, str):
        selected_contract = [selected_contract]
    dff = df[(df['经纪商名称'].isin(selected_brokers)) & 
             (df['年份'].isin(selected_year)) & 
             (df['合约名称'].isin(selected_contract))]
    if selected_long_short:
        dff = dff[dff['多/空头'].isin(selected_long_short)]
    if selected_action:
        dff = dff[dff['加/减仓'].isin(selected_action)]
    fig = go.Figure()
    for signal in display_signals:
        smooth_signal = dff[signal].rolling(window=window_size, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=smooth_signal,
            mode='lines',
            name=signal,
            line=dict(width=1.5),
            opacity=0.4
        ))
    if 'show_avg' in show_avg and len(display_signals) > 1:
        avg_values = dff[display_signals].mean(axis=1).rolling(window=window_size, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=avg_values,
            mode='lines',
            name='平均值',
            line=dict(color='black', width=3, dash='dash')
        ))
    # 参考线画在右轴
    fig = add_reference_lines(fig, dff, show_ref, yaxis_id='y3')
    fig.update_layout(
        title='基本面信号',
        height=400,
        hovermode='x unified',
        showlegend=True,
        margin=dict(l=60, r=60, t=60, b=60),
        yaxis=dict(
            title='指标',
            side='left'
        ),
        yaxis3=dict(
            title='参考线',
            side='right',
            overlaying='y',
            tickformat='.2f'
        )
    )
    return fig

# 更新趋势类指标图表
@app.callback(
    Output('trend-chart', 'figure'),
    [Input('broker-dropdown', 'value'),
     Input('year-dropdown', 'value'),
     Input('long-short-dropdown', 'value'),
     Input('action-dropdown', 'value'),
     Input('contract-dropdown', 'value'),
     Input('trend-control', 'value'),
     Input('trend-avg-control', 'value'),
     Input('trend-ref-control', 'value'),
     Input('smoothing-window', 'value')]
)
def update_trend_chart(selected_brokers, selected_year, selected_long_short, selected_action,
                       selected_contract, display_signals, show_avg, show_ref, window_size):
    if not selected_brokers or not selected_year or not selected_contract or not display_signals:
        return go.Figure()
    if isinstance(selected_year, int):
        selected_year = [selected_year]
    if isinstance(selected_contract, str):
        selected_contract = [selected_contract]
    dff = df[(df['经纪商名称'].isin(selected_brokers)) & 
             (df['年份'].isin(selected_year)) & 
             (df['合约名称'].isin(selected_contract))]
    if selected_long_short:
        dff = dff[dff['多/空头'].isin(selected_long_short)]
    if selected_action:
        dff = dff[dff['加/减仓'].isin(selected_action)]
    fig = go.Figure()
    for signal in display_signals:
        smooth_signal = dff[signal].rolling(window=window_size, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=smooth_signal,
            mode='lines',
            name=signal,
            line=dict(width=1.5),
            opacity=0.4

        ))
    if 'show_avg' in show_avg and len(display_signals) > 1:
        avg_values = dff[display_signals].mean(axis=1).rolling(window=window_size, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=avg_values,
            mode='lines',
            name='平均值',
            line=dict(color='black', width=3, dash='dash')
        ))
    fig = add_reference_lines(fig, dff, show_ref, yaxis_id='y3')
    fig.update_layout(
        title='趋势类指标',
        height=400,
        hovermode='x unified',
        showlegend=True,
        margin=dict(l=60, r=60, t=60, b=60),
        yaxis=dict(
            title='指标',
            side='left'
        ),
        yaxis3=dict(
            title='参考线',
            side='right',
            overlaying='y',
            tickformat='.2f'
        )
    )
    return fig

# 更新震荡类指标图表
@app.callback(
    Output('oscillator-chart', 'figure'),
    [Input('broker-dropdown', 'value'),
     Input('year-dropdown', 'value'),
     Input('long-short-dropdown', 'value'),
     Input('action-dropdown', 'value'),
     Input('contract-dropdown', 'value'),
     Input('oscillator-control', 'value'),
     Input('oscillator-avg-control', 'value'),
     Input('oscillator-ref-control', 'value'),
     Input('smoothing-window', 'value')]
)
def update_oscillator_chart(selected_brokers, selected_year, selected_long_short, selected_action,
                           selected_contract, display_signals, show_avg, show_ref, window_size):
    if not selected_brokers or not selected_year or not selected_contract or not display_signals:
        return go.Figure()
    if isinstance(selected_year, int):
        selected_year = [selected_year]
    if isinstance(selected_contract, str):
        selected_contract = [selected_contract]
    dff = df[(df['经纪商名称'].isin(selected_brokers)) & 
             (df['年份'].isin(selected_year)) & 
             (df['合约名称'].isin(selected_contract))]
    if selected_long_short:
        dff = dff[dff['多/空头'].isin(selected_long_short)]
    if selected_action:
        dff = dff[dff['加/减仓'].isin(selected_action)]
    fig = go.Figure()
    for signal in display_signals:
        smooth_signal = dff[signal].rolling(window=window_size, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=smooth_signal,
            mode='lines',
            name=signal,
            line=dict(width=1.5),
            opacity=0.4
        ))
    if 'show_avg' in show_avg and len(display_signals) > 1:
        avg_values = dff[display_signals].mean(axis=1).rolling(window=window_size, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=avg_values,
            mode='lines',
            name='平均值',
            line=dict(color='black', width=3, dash='dash')
        ))
    fig = add_reference_lines(fig, dff, show_ref, yaxis_id='y3')
    fig.update_layout(
        title='震荡类指标',
        height=400,
        hovermode='x unified',
        showlegend=True,
        margin=dict(l=60, r=60, t=60, b=60),
        yaxis=dict(
            title='指标',
            side='left'
        ),
        yaxis3=dict(
            title='参考线',
            side='right',
            overlaying='y',
            tickformat='.2f'
        )
    )
    return fig

@app.callback(
    Output('volume-chart', 'figure'),
    [Input('broker-dropdown', 'value'),
     Input('year-dropdown', 'value'),
     Input('long-short-dropdown', 'value'),
     Input('action-dropdown', 'value'),
     Input('contract-dropdown', 'value'),
     Input('volume-control', 'value'),
     Input('volume-avg-control', 'value'),
     Input('volume-ref-control', 'value'),
     Input('smoothing-window', 'value')]
)
def update_volume_chart(selected_brokers, selected_year, selected_long_short, selected_action,
                        selected_contract, display_signals, show_avg, show_ref, window_size):
    if not selected_brokers or not selected_year or not selected_contract or not display_signals:
        return go.Figure()
    
    if isinstance(selected_year, int):
        selected_year = [selected_year]
    if isinstance(selected_contract, str):
        selected_contract = [selected_contract]
    
    dff = df[
        (df['经纪商名称'].isin(selected_brokers)) &
        (df['年份'].isin(selected_year)) &
        (df['合约名称'].isin(selected_contract))
    ]
    if selected_long_short:
        dff = dff[dff['多/空头'].isin(selected_long_short)]
    if selected_action:
        dff = dff[dff['加/减仓'].isin(selected_action)]
    
    fig = go.Figure()
    for signal in display_signals:
        smooth_signal = dff[signal].rolling(window=window_size, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=smooth_signal,
            mode='lines',
            name=signal,
            line=dict(width=1.5),
            opacity=0.4
        ))
    
    if 'show_avg' in show_avg and len(display_signals) > 1:
        avg_values = dff[display_signals].mean(axis=1).rolling(window=window_size, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=dff['日期'], y=avg_values,
            mode='lines',
            name='平均值',
            line=dict(color='black', width=3, dash='dash')
        ))
    
    fig = add_reference_lines(fig, dff, show_ref, yaxis_id='y3')
    
    fig.update_layout(
        title='量能类指标',
        height=400,
        hovermode='x unified',
        showlegend=True,
        margin=dict(l=60, r=60, t=60, b=60),
        yaxis=dict(title='指标', side='left'),
        yaxis3=dict(title='参考线', side='right', overlaying='y', tickformat='.2f')
    )
    return fig


# 更新热力图
@app.callback(
    Output('heatmap-all', 'figure'),
    [Input('broker-dropdown', 'value'),
     Input('year-dropdown', 'value'),
     Input('long-short-dropdown', 'value'),
     Input('action-dropdown', 'value'),
     Input('contract-dropdown', 'value')]
)
def update_heatmap(selected_brokers, selected_year, selected_long_short, selected_action, selected_contract):
    if not selected_brokers or not selected_year or not selected_contract:
        return go.Figure()
    if isinstance(selected_year, int):
        selected_year = [selected_year]
    if isinstance(selected_contract, str):
        selected_contract = [selected_contract]
    dff = df[(df['经纪商名称'].isin(selected_brokers)) & 
             (df['年份'].isin(selected_year)) & 
             (df['合约名称'].isin(selected_contract))]
    if selected_long_short:
        dff = dff[dff['多/空头'].isin(selected_long_short)]
    if selected_action:
        dff = dff[dff['加/减仓'].isin(selected_action)]
    sub_df = dff[indicator_cols].dropna(how='all')
    if sub_df.empty:
        return go.Figure()
    corr_data = sub_df.corr()
    fig = px.imshow(
        corr_data,
        text_auto=".2f",
        color_continuous_scale='RdBu_r',
        zmin=-1,
        zmax=1,
        aspect="auto"
    )
    fig.update_layout(
        title="所有指标相关性热力图",
        height=1000,
        width=1200,
        font=dict(size=14),
        margin=dict(l=60, r=60, t=60, b=60)
    )
    return fig

# # 读取SHAP数据
# shap_summary_df = pd.read_csv("D:\\KaraJC的文件夹\\快学\\Intern\\LDC\\信号\\SHAP单权重，交互重要性\\SHAP百分比影响权重.csv")
# shap_summary_df.set_index(shap_summary_df.columns[0], inplace=True)

# @app.callback(
#     Output('shap-action-heatmap', 'figure'),
#     Input('contract-dropdown', 'value')
# )
# def display_shap_action_heatmap(contract):
#     fig = px.imshow(
#         shap_summary_df,
#         color_continuous_scale='Reds',
#         text_auto=".2f",
#         labels=dict(x="仓位行为", y="信号", color="平均SHAP值"),
#         aspect="auto"
#     )
#     fig.update_layout(title="各信号对加/减仓的解释强度（平均SHAP值）", height=800)
#     return fig



if __name__ == '__main__':
    app.run(debug=True)
