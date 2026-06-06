-- 统一数据库默认时区为东八区，避免管理端和 psql 直接查看时显示为 UTC。

ALTER DATABASE opendevflow SET timezone = 'Asia/Shanghai';
ALTER ROLE "user_ArNNMG" SET timezone = 'Asia/Shanghai';
