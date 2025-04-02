import nltk
import ssl

try:
    # 尝试创建未经验证的 SSL 上下文 (有安全风险，仅用于下载)
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # 如果 Python 版本较低，可能没有 _create_unverified_context
    pass
else:
    # 应用未经验证的上下文
    ssl._create_default_https_context = _create_unverified_https_context

print("尝试下载 NLTK 'punkt' 数据包...")
try:
    nltk.download('punkt')
    nltk.download('punkt_tab')
    nltk.download('all')
    print("NLTK 'punkt' 下载成功！")
except Exception as e:
    print(f"下载 NLTK 'punkt' 时出错: {e}")
    print("请检查网络连接和防火墙设置。")

# 注意：下载完成后，理论上 ssl._create_default_https_context
# 应该恢复，但为保险起见，您可以在主脚本运行前仅执行一次此下载脚本。