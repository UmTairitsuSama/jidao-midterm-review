# 计导期中复习

桌面首页集中展示学习进度与分类入口；点击题目进入独立作答界面，左侧题目列表可折叠，支持上一题 / 下一题。保留本机自动保存、错题本、模拟考试和数据备份。

## 构建与验证

```sh
python build.py --out index.html
node tools/ui_test.mjs index.html
```

源码位于 app/，题目数据位于 content/。index.html 可离线使用。旧版页面地址会跳转至对应的新视图。本机存储继续使用 cd_review_v2。
