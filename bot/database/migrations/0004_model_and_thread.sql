-- Модель устройства (iPhone 13, MacBook Air M2 и т.п.)
ALTER TABLE orders ADD COLUMN device_model TEXT;

-- ID сообщения-уведомления у мастера. Используем как корень "треда":
-- все последующие сообщения по заявке (фото, реплики клиента, ответы
-- мастера, смены статуса) отправляются с reply_to_message_id = этот id,
-- чтобы в чате с мастером визуально была видна ветка по каждой заявке.
ALTER TABLE orders ADD COLUMN notification_message_id INTEGER;
