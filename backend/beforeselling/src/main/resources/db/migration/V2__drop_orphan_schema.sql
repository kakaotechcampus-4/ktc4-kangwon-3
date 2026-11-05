DROP TABLE IF EXISTS public.agent_review;

ALTER TABLE public.product DROP COLUMN IF EXISTS diagnosis_round;

ALTER TABLE public.product_progress DROP CONSTRAINT IF EXISTS product_progress_tool_name_check;
ALTER TABLE public.product_progress ADD CONSTRAINT product_progress_tool_name_check
    CHECK (tool_name IN ('CUSTOMS', 'CHILDREN', 'ELECTRICAL', 'RADIO', 'FOOD_DRUG', 'LABEL_AD'));

ALTER TABLE public.product_tool_review DROP CONSTRAINT IF EXISTS product_tool_review_tool_name_check;
ALTER TABLE public.product_tool_review ADD CONSTRAINT product_tool_review_tool_name_check
    CHECK (tool_name IN ('CUSTOMS', 'CHILDREN', 'ELECTRICAL', 'RADIO', 'FOOD_DRUG', 'LABEL_AD'));
