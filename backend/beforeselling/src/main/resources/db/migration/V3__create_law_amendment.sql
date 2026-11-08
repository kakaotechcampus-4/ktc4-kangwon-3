CREATE TABLE public.law_amendment (
    law_amendment_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    law_name character varying(255) NOT NULL,
    document_id character varying(50) NOT NULL,
    admrul boolean NOT NULL,
    tool_name character varying(255) NOT NULL,
    serial_number character varying(50) NOT NULL,
    previous_serial_number character varying(50),
    revision_type character varying(50),
    enforce_date date,
    issued_date date,
    CONSTRAINT law_amendment_pkey PRIMARY KEY (law_amendment_id),
    CONSTRAINT uk_law_amendment_document_id_serial_number UNIQUE (document_id, serial_number),
    CONSTRAINT law_amendment_tool_name_check
        CHECK (tool_name IN ('CUSTOMS', 'CHILDREN', 'ELECTRICAL', 'RADIO', 'FOOD_DRUG', 'LABEL_AD'))
);

CREATE TABLE public.law_amendment_product (
    law_amendment_product_id uuid NOT NULL,
    created_at timestamp(6) without time zone NOT NULL,
    updated_at timestamp(6) without time zone NOT NULL,
    law_amendment_id uuid NOT NULL,
    product_id uuid NOT NULL,
    CONSTRAINT law_amendment_product_pkey PRIMARY KEY (law_amendment_product_id),
    CONSTRAINT uk_law_amendment_product_law_amendment_id_product_id UNIQUE (law_amendment_id, product_id),
    CONSTRAINT fk_law_amendment_product_law_amendment_id
        FOREIGN KEY (law_amendment_id) REFERENCES public.law_amendment (law_amendment_id) ON DELETE CASCADE,
    CONSTRAINT fk_law_amendment_product_product_id
        FOREIGN KEY (product_id) REFERENCES public.product (product_id) ON DELETE CASCADE
);

CREATE INDEX idx_law_amendment_product_product_id ON public.law_amendment_product USING btree (product_id);

ALTER TABLE public.users ADD COLUMN law_amendment_alert_enabled boolean DEFAULT true NOT NULL;
