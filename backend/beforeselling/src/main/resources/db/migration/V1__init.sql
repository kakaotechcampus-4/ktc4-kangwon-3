-- Baseline: Flyway 도입 시점(#149)의 엔티티 스키마. pg_dump --schema-only로 생성.

CREATE TABLE public.diagnoses (
    diagnoses_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    processing_status character varying(255) NOT NULL,
    user_id uuid NOT NULL,
    CONSTRAINT diagnoses_processing_status_check CHECK (((processing_status)::text = ANY ((ARRAY['PENDING'::character varying, 'IN_PROGRESS'::character varying, 'AWAITING_INPUT'::character varying, 'COMPLETED'::character varying, 'FAILED'::character varying])::text[])))
);

CREATE TABLE public.finding_legal_source (
    finding_legal_source_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    article character varying(255),
    effective_date character varying(50),
    law_name character varying(255),
    quoted_text text,
    sort_order integer NOT NULL,
    source_name character varying(255) NOT NULL,
    source_url text,
    product_finding_id uuid NOT NULL
);

CREATE TABLE public.product (
    product_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    assessment_status character varying(255),
    error_code character varying(50),
    error_message text,
    error_retryable boolean,
    failed_stage character varying(255),
    processing_status character varying(255) NOT NULL,
    product_image_key text,
    product_name character varying(255) NOT NULL,
    requested_at timestamp(6) without time zone,
    result_status character varying(255),
    resume_pending_since timestamp(6) without time zone,
    run_id character varying(255),
    sort_order integer NOT NULL,
    source_text text,
    source_type character varying(255) NOT NULL,
    source_url text,
    summary text,
    diagnoses_id uuid NOT NULL,
    CONSTRAINT product_assessment_status_check CHECK (((assessment_status)::text = ANY ((ARRAY['COMPLETED'::character varying, 'INCOMPLETE'::character varying])::text[]))),
    CONSTRAINT product_failed_stage_check CHECK (((failed_stage)::text = ANY ((ARRAY['EXTRACTION'::character varying, 'SELECTION'::character varying, 'TOOL_EXECUTION'::character varying, 'AGGREGATION'::character varying, 'VERIFICATION'::character varying, 'FINALIZATION'::character varying])::text[]))),
    CONSTRAINT product_processing_status_check CHECK (((processing_status)::text = ANY ((ARRAY['PENDING'::character varying, 'IN_PROGRESS'::character varying, 'AWAITING_INPUT'::character varying, 'COMPLETED'::character varying, 'FAILED'::character varying])::text[]))),
    CONSTRAINT product_result_status_check CHECK (((result_status)::text = ANY ((ARRAY['PURCHASING_AGENT_ALLOWED'::character varying, 'DIRECT_IMPORT_CERTIFICATION_REQUIRED'::character varying, 'RECHECK_REQUIRED'::character varying])::text[]))),
    CONSTRAINT product_source_type_check CHECK (((source_type)::text = ANY ((ARRAY['URL'::character varying, 'TEXT_IMAGE'::character varying])::text[])))
);

CREATE TABLE public.product_finding (
    product_finding_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    determination character varying(255) NOT NULL,
    rationale text NOT NULL,
    risk_level character varying(255) NOT NULL,
    sort_order integer NOT NULL,
    subject character varying(255) NOT NULL,
    summary text NOT NULL,
    product_tool_review_id uuid NOT NULL,
    CONSTRAINT product_finding_determination_check CHECK (((determination)::text = ANY ((ARRAY['REQUIRED'::character varying, 'NOT_REQUIRED'::character varying, 'POSSIBLY_REQUIRED'::character varying, 'INSUFFICIENT_INFORMATION'::character varying, 'NOT_APPLICABLE'::character varying])::text[]))),
    CONSTRAINT product_finding_risk_level_check CHECK (((risk_level)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'UNKNOWN'::character varying])::text[])))
);

CREATE TABLE public.product_image (
    product_image_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    image_key text NOT NULL,
    sort_order integer NOT NULL,
    product_id uuid NOT NULL
);

CREATE TABLE public.product_notice (
    product_id uuid NOT NULL,
    notice_text text NOT NULL,
    notice_order integer NOT NULL,
    CONSTRAINT product_notice_notice_order_check CHECK ((notice_order >= 0))
);

CREATE TABLE public.product_progress (
    product_progress_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    run_id character varying(255) NOT NULL,
    sequence integer NOT NULL,
    stage character varying(255) NOT NULL,
    stage_status character varying(255) NOT NULL,
    tool_name character varying(255),
    product_id uuid NOT NULL,
    CONSTRAINT product_progress_stage_check CHECK (((stage)::text = ANY ((ARRAY['EXTRACTION'::character varying, 'SELECTION'::character varying, 'TOOL_EXECUTION'::character varying, 'AGGREGATION'::character varying, 'VERIFICATION'::character varying, 'FINALIZATION'::character varying])::text[]))),
    CONSTRAINT product_progress_stage_status_check CHECK (((stage_status)::text = ANY ((ARRAY['STARTED'::character varying, 'COMPLETED'::character varying, 'SKIPPED'::character varying])::text[]))),
    CONSTRAINT product_progress_tool_name_check CHECK (((tool_name)::text = ANY ((ARRAY['CUSTOMS'::character varying, 'CHILDREN'::character varying, 'ELECTRICAL'::character varying, 'RADIO'::character varying, 'FOOD_DRUG'::character varying, 'LABEL_AD'::character varying])::text[])))
);

CREATE TABLE public.product_question (
    product_question_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    answer_text text,
    help_text text,
    question_key character varying(50) NOT NULL,
    question_order integer NOT NULL,
    question_round integer DEFAULT 1 NOT NULL,
    question_text text NOT NULL,
    product_id uuid NOT NULL
);

CREATE TABLE public.product_required_action (
    product_id uuid NOT NULL,
    action_text text NOT NULL,
    action_order integer NOT NULL,
    CONSTRAINT product_required_action_action_order_check CHECK ((action_order >= 0))
);

CREATE TABLE public.product_tool_review (
    product_tool_review_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    message text,
    status character varying(255) NOT NULL,
    tool_name character varying(255) NOT NULL,
    product_id uuid NOT NULL,
    CONSTRAINT product_tool_review_status_check CHECK (((status)::text = ANY ((ARRAY['COMPLETED'::character varying, 'SKIPPED'::character varying, 'INCOMPLETE'::character varying])::text[]))),
    CONSTRAINT product_tool_review_tool_name_check CHECK (((tool_name)::text = ANY ((ARRAY['CUSTOMS'::character varying, 'CHILDREN'::character varying, 'ELECTRICAL'::character varying, 'RADIO'::character varying, 'FOOD_DRUG'::character varying, 'LABEL_AD'::character varying])::text[])))
);

CREATE TABLE public.s3_files (
    s3_file_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    key character varying(512) NOT NULL,
    status character varying(255) NOT NULL,
    CONSTRAINT s3_files_status_check CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'CONFIRMED'::character varying])::text[])))
);

CREATE TABLE public.users (
    user_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    email character varying(255),
    name character varying(255) NOT NULL,
    role character varying(255) NOT NULL,
    social_id character varying(255) NOT NULL,
    social_provider character varying(255) NOT NULL,
    social_refresh_token text,
    CONSTRAINT users_role_check CHECK (((role)::text = ANY ((ARRAY['USER'::character varying, 'ADMIN'::character varying])::text[]))),
    CONSTRAINT users_social_provider_check CHECK (((social_provider)::text = ANY ((ARRAY['KAKAO'::character varying, 'NAVER'::character varying, 'GOOGLE'::character varying])::text[])))
);

ALTER TABLE ONLY public.diagnoses
    ADD CONSTRAINT diagnoses_pkey PRIMARY KEY (diagnoses_id);

ALTER TABLE ONLY public.finding_legal_source
    ADD CONSTRAINT finding_legal_source_pkey PRIMARY KEY (finding_legal_source_id);

ALTER TABLE ONLY public.product_finding
    ADD CONSTRAINT product_finding_pkey PRIMARY KEY (product_finding_id);

ALTER TABLE ONLY public.product_image
    ADD CONSTRAINT product_image_pkey PRIMARY KEY (product_image_id);

ALTER TABLE ONLY public.product_notice
    ADD CONSTRAINT product_notice_pkey PRIMARY KEY (product_id, notice_order);

ALTER TABLE ONLY public.product
    ADD CONSTRAINT product_pkey PRIMARY KEY (product_id);

ALTER TABLE ONLY public.product_progress
    ADD CONSTRAINT product_progress_pkey PRIMARY KEY (product_progress_id);

ALTER TABLE ONLY public.product_question
    ADD CONSTRAINT product_question_pkey PRIMARY KEY (product_question_id);

ALTER TABLE ONLY public.product_required_action
    ADD CONSTRAINT product_required_action_pkey PRIMARY KEY (product_id, action_order);

ALTER TABLE ONLY public.product_tool_review
    ADD CONSTRAINT product_tool_review_pkey PRIMARY KEY (product_tool_review_id);

ALTER TABLE ONLY public.s3_files
    ADD CONSTRAINT s3_files_pkey PRIMARY KEY (s3_file_id);

ALTER TABLE ONLY public.product_question
    ADD CONSTRAINT uk_product_question_product_id_round_key UNIQUE (product_id, question_round, question_key);

ALTER TABLE ONLY public.product_tool_review
    ADD CONSTRAINT uk_product_tool_review_product_id_tool_name UNIQUE (product_id, tool_name);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uk_users_social UNIQUE (social_provider, social_id);

ALTER TABLE ONLY public.s3_files
    ADD CONSTRAINT ukpada3s2fjcapy8cuc9ow9g4pu UNIQUE (key);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);

CREATE INDEX idx_diagnoses_user_id_created_at ON public.diagnoses USING btree (user_id, created_at);

CREATE INDEX idx_finding_legal_source_finding_id_sort_order ON public.finding_legal_source USING btree (product_finding_id, sort_order);

CREATE INDEX idx_product_diagnoses_id_sort_order ON public.product USING btree (diagnoses_id, sort_order);

CREATE INDEX idx_product_finding_tool_review_id_sort_order ON public.product_finding USING btree (product_tool_review_id, sort_order);

CREATE INDEX idx_product_image_product_id ON public.product_image USING btree (product_id);

CREATE INDEX idx_product_processing_status_updated_at ON public.product USING btree (processing_status, updated_at);

CREATE INDEX idx_product_progress_product_id ON public.product_progress USING btree (product_id);

CREATE INDEX idx_product_resume_pending_since ON public.product USING btree (resume_pending_since);

CREATE INDEX idx_s3_files_status_created_at ON public.s3_files USING btree (status, created_at);

ALTER TABLE ONLY public.product_progress
    ADD CONSTRAINT fk66i94ncxtk6k0xbfc1m2ewve1 FOREIGN KEY (product_id) REFERENCES public.product(product_id);

ALTER TABLE ONLY public.product_image
    ADD CONSTRAINT fk6oo0cvcdtb6qmwsga468uuukk FOREIGN KEY (product_id) REFERENCES public.product(product_id);

ALTER TABLE ONLY public.product_tool_review
    ADD CONSTRAINT fkc7vhqv55lg2tccod6a6n0n9iv FOREIGN KEY (product_id) REFERENCES public.product(product_id);

ALTER TABLE ONLY public.product
    ADD CONSTRAINT fkfhf7fbrbxcpr5j34ufdkmiald FOREIGN KEY (diagnoses_id) REFERENCES public.diagnoses(diagnoses_id);

ALTER TABLE ONLY public.product_notice
    ADD CONSTRAINT fkgtgh1sdrdnb5go3mq6hvvuq44 FOREIGN KEY (product_id) REFERENCES public.product(product_id);

ALTER TABLE ONLY public.product_required_action
    ADD CONSTRAINT fkhwaxrguyqc9ujsn40kurarmw6 FOREIGN KEY (product_id) REFERENCES public.product(product_id);

ALTER TABLE ONLY public.product_question
    ADD CONSTRAINT fkotbqj9u64wq8jwnhcuixjci2q FOREIGN KEY (product_id) REFERENCES public.product(product_id);

ALTER TABLE ONLY public.product_finding
    ADD CONSTRAINT fkpvehv8ags5usy96i3546vmjle FOREIGN KEY (product_tool_review_id) REFERENCES public.product_tool_review(product_tool_review_id);

ALTER TABLE ONLY public.finding_legal_source
    ADD CONSTRAINT fkq8q54g5gyu2ok172g0pfbbhom FOREIGN KEY (product_finding_id) REFERENCES public.product_finding(product_finding_id);

