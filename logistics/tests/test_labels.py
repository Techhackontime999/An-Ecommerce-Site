"""Tests for PDF document generation."""

import io

from PIL import Image

from logistics.models import Shipment, ShipmentItem
from logistics.services.labels import (
    attach_label,
    generate_invoice_pdf,
    generate_label_pdf,
    generate_manifest_pdf,
    generate_pickup_sheet_pdf,
)

from .base import LogisticsTestCase


class LabelTests(LogisticsTestCase):

    def setUp(self):
        super().setUp()
        self.shipment = Shipment.objects.create(
            order=self.order,
            seller=self.seller,
            warehouse=self.warehouse,
            courier=self.mock,
            tracking_number='MOCK999999999',
            payment_mode='prepaid',
            length_cm='20',
            width_cm='15',
            height_cm='10',
            weight_g='500',
            source_pincode=self.warehouse.pincode,
            destination_pincode=self.PINCODE,
        )
        ShipmentItem.objects.create(
            shipment=self.shipment,
            product=self.product,
            product_name='Test Product',
            sku='TP-1',
            quantity=2,
            weight_g='500',
            unit_price='999.00',
        )

    def test_label_pdf_is_valid(self):
        data = generate_label_pdf(self.shipment)
        self.assertTrue(data.startswith(b'%PDF'))
        self.assertGreater(len(data), 1000)

    def test_label_qr_encodes_a_tracking_target(self):
        data = generate_label_pdf(self.shipment)
        self.assertIn(b'PDF', data)

    def test_attach_label_saves_file(self):
        name = attach_label(self.shipment, overwrite=True)
        self.assertIn('logistics/labels/', name)
        self.shipment.refresh_from_db()
        self.assertTrue(self.shipment.label.name)

    def test_invoice_pdf(self):
        data = generate_invoice_pdf(self.shipment)
        self.assertTrue(data.startswith(b'%PDF'))

    def test_manifest_pdf(self):
        data = generate_manifest_pdf([self.shipment.pk])
        self.assertTrue(data.startswith(b'%PDF'))

    def test_pickup_sheet_pdf(self):
        data = generate_pickup_sheet_pdf([self.shipment])
        self.assertTrue(data.startswith(b'%PDF'))
