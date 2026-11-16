-- qc-hub 慢请求对应的送检查询。可重复执行前先看索引是否已在。
-- 列表：WHERE project_id=? AND deleted_at IS NULL ORDER BY submit_date DESC, code DESC
ALTER TABLE sampling_submissions
  ADD INDEX idx_sampling_list (project_id, deleted_at, submit_date, code);

-- 带送检单位：再加 department 等值条件
ALTER TABLE sampling_submissions
  ADD INDEX idx_sampling_dept_list (project_id, deleted_at, department, submit_date, code);

-- 同一天、同部番取最大送检次数
ALTER TABLE sampling_submissions
  ADD INDEX idx_sampling_part_day (project_id, part_no, deleted_at, submit_date);
